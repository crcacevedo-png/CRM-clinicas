"""Auto-extracted from server.py — DO NOT EDIT MANUALLY without checking server.py."""
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

router = APIRouter()

from core import sdb, supabase_admin, require_clinic_member, require_finance_role, now_iso, logger
from routes.expenses import EXPENSE_CATEGORY_LABELS

# ============== FINANCIAL REPORTS ROUTES ==============

def _period_dates(period: str, date_from: str = "", date_to: str = ""):
    """Resolve date range from a period preset or custom from/to."""
    from datetime import datetime as dt, date as dt_date
    today = dt.now(timezone.utc).date()
    if period == 'custom' and date_from and date_to:
        return date_from, date_to
    if period == 'previous_month':
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.isoformat(), last_prev.isoformat()
    if period == 'quarter':
        q = (today.month - 1) // 3
        first = today.replace(month=q * 3 + 1, day=1)
        return first.isoformat(), today.isoformat()
    if period == 'year':
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    # default current_month
    return today.replace(day=1).isoformat(), today.isoformat()

def _previous_period(date_from: str, date_to: str):
    from datetime import date as dt_date
    a = dt_date.fromisoformat(date_from)
    b = dt_date.fromisoformat(date_to)
    span = (b - a).days + 1
    pa = a - timedelta(days=span)
    pb = a - timedelta(days=1)
    return pa.isoformat(), pb.isoformat()

@router.get("/clinic/reports/executive-summary")
async def executive_summary(
    period: str = "current_month", date_from: str = "", date_to: str = "",
    branch_id: str = "", ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    require_finance_role(ctx)
    try:
        d_from, d_to = _period_dates(period, date_from, date_to)
        prev_from, prev_to = _previous_period(d_from, d_to)
        # Sales for current and previous period
        def fetch_sales(df, dt_):
            q = sdb.table('sales').select('id,total,amount_due,patient_id,created_at,branch_id').eq('clinic_id', clinic_id).neq('status', 'cancelled').gte('created_at', df).lte('created_at', dt_ + 'T23:59:59Z')
            if branch_id: q = q.eq('branch_id', branch_id)
            return q.execute().data or []
        cur_sales = fetch_sales(d_from, d_to)
        prev_sales = fetch_sales(prev_from, prev_to)
        # Expenses
        def fetch_expenses(df, dt_):
            q = sdb.table('expenses').select('total,category').eq('clinic_id', clinic_id).gte('expense_date', df).lte('expense_date', dt_)
            if branch_id: q = q.eq('branch_id', branch_id)
            return q.execute().data or []
        cur_exp = fetch_expenses(d_from, d_to)
        prev_exp = fetch_expenses(prev_from, prev_to)
        # AR pending
        ar_balance = sum(float(a.get('balance') or 0) for a in (sdb.table('accounts_receivable').select('balance').eq('clinic_id', clinic_id).neq('status', 'paid').execute().data or []))
        # Patients new in period
        pat_q = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic_id).gte('created_at', d_from).lte('created_at', d_to + 'T23:59:59Z').execute()
        new_patients = pat_q.count or 0
        # Appointments in period
        app_count = 0
        try:
            ap = sdb.table('appointments').select('id', count='exact').eq('clinic_id', clinic_id).gte('starts_at', d_from).lte('starts_at', d_to + 'T23:59:59Z')
            if branch_id: ap = ap.eq('branch_id', branch_id)
            app_count = ap.execute().count or 0
        except Exception:
            pass
        # Compute KPIs
        income = round(sum(float(s.get('total') or 0) for s in cur_sales), 2)
        prev_income = round(sum(float(s.get('total') or 0) for s in prev_sales), 2)
        expenses_total = round(sum(float(e.get('total') or 0) for e in cur_exp), 2)
        prev_expenses = round(sum(float(e.get('total') or 0) for e in prev_exp), 2)
        # Commissions
        comm = sdb.table('commissions_earned').select('commission_amount').eq('clinic_id', clinic_id).gte('earned_at', d_from).lte('earned_at', d_to + 'T23:59:59Z').execute().data or []
        comm_total = round(sum(float(c.get('commission_amount') or 0) for c in comm), 2)
        # Net profit (income - expenses - commissions)
        net = round(income - expenses_total - comm_total, 2)
        margin = (net / income * 100) if income > 0 else 0
        avg_ticket = (income / len(cur_sales)) if cur_sales else 0

        # Trend: last 12 months income vs expenses
        from datetime import date as dt_date
        from dateutil.relativedelta import relativedelta
        today_d = dt_date.today()
        trend = []
        for i in range(11, -1, -1):
            month_first = (today_d.replace(day=1) - relativedelta(months=i))
            next_first = month_first + relativedelta(months=1)
            ms = sdb.table('sales').select('total').eq('clinic_id', clinic_id).neq('status', 'cancelled').gte('created_at', month_first.isoformat()).lt('created_at', next_first.isoformat()).execute().data or []
            me = sdb.table('expenses').select('total').eq('clinic_id', clinic_id).gte('expense_date', month_first.isoformat()).lt('expense_date', next_first.isoformat()).execute().data or []
            trend.append({
                "month": month_first.strftime('%Y-%m'),
                "income": round(sum(float(x.get('total') or 0) for x in ms), 2),
                "expenses": round(sum(float(x.get('total') or 0) for x in me), 2),
            })

        # Income by payment method (current period)
        sale_ids = [s['id'] for s in cur_sales]
        by_method = {}
        if sale_ids:
            pays = sdb.table('payments').select('amount,payment_method').in_('sale_id', sale_ids).execute().data or []
            for p in pays:
                m = p.get('payment_method') or 'other'
                by_method[m] = round(by_method.get(m, 0) + float(p.get('amount') or 0), 2)
        # Expenses by category
        cat_totals = {}
        for e in cur_exp:
            k = e.get('category') or 'other'
            cat_totals[k] = round(cat_totals.get(k, 0) + float(e.get('total') or 0), 2)
        cat_breakdown = [{"key": k, "label": EXPENSE_CATEGORY_LABELS.get(k, k), "amount": v} for k, v in cat_totals.items()]
        cat_breakdown.sort(key=lambda x: x['amount'], reverse=True)
        # Income by branch
        by_branch = {}
        for s in cur_sales:
            b = s.get('branch_id')
            if b: by_branch[b] = round(by_branch.get(b, 0) + float(s.get('total') or 0), 2)
        # Pre-fetch branch dictionary in one query
        branch_dict = {}
        if by_branch:
            branch_rows = sdb.table('branches').select('id,name').in_('id', list(by_branch.keys())).execute().data or []
            branch_dict = {b['id']: b['name'] for b in branch_rows}
        branch_list = [{"branch_id": bid, "branch_name": branch_dict.get(bid, 'Sucursal'), "amount": amount} for bid, amount in by_branch.items()]
        branch_list.sort(key=lambda x: x['amount'], reverse=True)

        def pct_change(cur, prev):
            if prev == 0: return None
            return round((cur - prev) / prev * 100, 1)

        return {
            "period": {"from": d_from, "to": d_to},
            "kpis": {
                "income": {"value": income, "delta_pct": pct_change(income, prev_income)},
                "expenses": {"value": expenses_total, "delta_pct": pct_change(expenses_total, prev_expenses)},
                "net_profit": {"value": net, "margin_pct": round(margin, 1)},
                "ar_pending": round(ar_balance, 2),
                "avg_ticket": round(avg_ticket, 2),
                "new_patients": new_patients,
                "appointments": app_count,
                "sales_count": len(cur_sales),
            },
            "trend_12m": trend,
            "income_by_method": [{"method": k, "amount": v} for k, v in by_method.items()],
            "expenses_by_category": cat_breakdown,
            "income_by_branch": branch_list,
        }
    except Exception as e:
        logger.error(f"Executive summary error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/reports/income")
async def income_report(
    period: str = "current_month", date_from: str = "", date_to: str = "",
    branch_id: str = "", doctor_id: str = "",
    grouping: str = "day",  # day | week | month
    ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    require_finance_role(ctx)
    try:
        d_from, d_to = _period_dates(period, date_from, date_to)
        q = sdb.table('sales').select('id,total,created_at,branch_id,doctor_id,cashier_id').eq('clinic_id', clinic_id).neq('status', 'cancelled').gte('created_at', d_from).lte('created_at', d_to + 'T23:59:59Z')
        if branch_id: q = q.eq('branch_id', branch_id)
        if doctor_id: q = q.eq('doctor_id', doctor_id)
        sales = q.execute().data or []
        sale_ids = [s['id'] for s in sales]
        # Time series (day/week/month)
        from datetime import datetime as dt, date as dt_date, timedelta
        series = {}
        for s in sales:
            d = (s.get('created_at') or '')[:10]
            if not d: continue
            try:
                day = dt_date.fromisoformat(d)
            except Exception:
                continue
            if grouping == 'week':
                start = day - timedelta(days=day.weekday())
                k = start.isoformat()
            elif grouping == 'month':
                k = day.replace(day=1).isoformat()
            else:
                k = d
            series[k] = round(series.get(k, 0) + float(s.get('total') or 0), 2)
        time_series = [{"date": k, "amount": v} for k, v in sorted(series.items())]

        # Per-sale-item analysis: top products + top services
        items = []
        if sale_ids:
            items = sdb.table('sale_items').select('product_id,service_id,description,quantity,total').in_('sale_id', sale_ids).execute().data or []
        prod_totals = {}
        prod_qty = {}
        svc_totals = {}
        svc_qty = {}
        for it in items:
            qty = float(it.get('quantity') or 0)
            tot = float(it.get('total') or 0)
            if it.get('product_id'):
                pid = it['product_id']
                prod_totals[pid] = prod_totals.get(pid, 0) + tot
                prod_qty[pid] = prod_qty.get(pid, 0) + qty
            elif it.get('service_id'):
                sid = it['service_id']
                svc_totals[sid] = svc_totals.get(sid, 0) + tot
                svc_qty[sid] = svc_qty.get(sid, 0) + qty
        def top_n(totals, qtys, kind):
            arr = []
            for pid, amount in totals.items():
                if kind == 'product':
                    p = sdb.table('products').select('name,sku').eq('id', pid).maybe_single().execute()
                    p_data = getattr(p, 'data', None) if p else None
                    arr.append({"id": pid, "name": p_data['name'] if p_data else 'Producto', "sku": p_data.get('sku') if p_data else '', "quantity": qtys.get(pid, 0), "amount": round(amount, 2)})
                else:
                    s = sdb.table('services').select('name').eq('id', pid).maybe_single().execute()
                    s_data = getattr(s, 'data', None) if s else None
                    arr.append({"id": pid, "name": s_data['name'] if s_data else 'Servicio', "quantity": qtys.get(pid, 0), "amount": round(amount, 2)})
            arr.sort(key=lambda x: x['amount'], reverse=True)
            return arr[:10]
        top_products = top_n(prod_totals, prod_qty, 'product')
        top_services = top_n(svc_totals, svc_qty, 'service')

        # Income by doctor
        by_doctor = {}
        for s in sales:
            d = s.get('doctor_id')
            if not d: continue
            by_doctor[d] = round(by_doctor.get(d, 0) + float(s.get('total') or 0), 2)
        doctor_list = []
        for did, amount in by_doctor.items():
            mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', did).maybe_single().execute()
            mb_data = getattr(mb, 'data', None) if mb else None
            doctor_list.append({"doctor_id": did, "name": f"Dr(a). {mb_data['first_name']} {mb_data['last_name']}" if mb_data else 'Médico', "amount": amount})
        doctor_list.sort(key=lambda x: x['amount'], reverse=True)

        # Income by method
        by_method = {}
        if sale_ids:
            pays = sdb.table('payments').select('amount,payment_method').in_('sale_id', sale_ids).execute().data or []
            for p in pays:
                m = p.get('payment_method') or 'other'
                by_method[m] = round(by_method.get(m, 0) + float(p.get('amount') or 0), 2)

        return {
            "period": {"from": d_from, "to": d_to, "grouping": grouping},
            "total_income": round(sum(float(s.get('total') or 0) for s in sales), 2),
            "sales_count": len(sales),
            "time_series": time_series,
            "top_products": top_products,
            "top_services": top_services,
            "by_doctor": doctor_list,
            "by_method": [{"method": k, "amount": v} for k, v in by_method.items()],
        }
    except Exception as e:
        logger.error(f"Income report error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/reports/pnl")
async def pnl_report(
    period: str = "current_month", date_from: str = "", date_to: str = "",
    branch_id: str = "", ctx=Depends(require_clinic_member)
):
    """Estado de resultados (P&L) con comparación período actual vs anterior."""
    clinic_id = ctx["member"]["clinic_id"]
    require_finance_role(ctx)
    try:
        d_from, d_to = _period_dates(period, date_from, date_to)
        prev_from, prev_to = _previous_period(d_from, d_to)

        def compute(df, dt_):
            sq = sdb.table('sales').select('id,total').eq('clinic_id', clinic_id).neq('status', 'cancelled').gte('created_at', df).lte('created_at', dt_ + 'T23:59:59Z')
            if branch_id: sq = sq.eq('branch_id', branch_id)
            sales = sq.execute().data or []
            sale_ids = [s['id'] for s in sales]
            # Income split by service vs product
            svc_income = 0.0
            prod_income = 0.0
            cogs = 0.0
            if sale_ids:
                items = sdb.table('sale_items').select('product_id,service_id,quantity,total').in_('sale_id', sale_ids).execute().data or []
                for it in items:
                    tot = float(it.get('total') or 0)
                    qty = float(it.get('quantity') or 0)
                    if it.get('product_id'):
                        prod_income += tot
                        # COGS via product cost_price
                        p = sdb.table('products').select('cost_price').eq('id', it['product_id']).maybe_single().execute()
                        p_data = getattr(p, 'data', None) if p else None
                        if p_data and p_data.get('cost_price'):
                            cogs += float(p_data['cost_price']) * qty
                    elif it.get('service_id'):
                        svc_income += tot
            # Expenses by category
            eq = sdb.table('expenses').select('total,category').eq('clinic_id', clinic_id).gte('expense_date', df).lte('expense_date', dt_)
            if branch_id: eq = eq.eq('branch_id', branch_id)
            exps = eq.execute().data or []
            cat_totals = {}
            for e in exps:
                k = e.get('category') or 'other'
                cat_totals[k] = cat_totals.get(k, 0) + float(e.get('total') or 0)
            # Commissions
            comm = sdb.table('commissions_earned').select('commission_amount').eq('clinic_id', clinic_id).gte('earned_at', df).lte('earned_at', dt_ + 'T23:59:59Z').execute().data or []
            comm_total = sum(float(c.get('commission_amount') or 0) for c in comm)
            total_income = svc_income + prod_income
            gross_margin = total_income - cogs
            total_expenses = sum(cat_totals.values())
            ebt = gross_margin - total_expenses
            net = ebt - comm_total
            return {
                "income": {"services": round(svc_income, 2), "products": round(prod_income, 2), "other": 0.0, "total": round(total_income, 2)},
                "cogs": round(cogs, 2),
                "gross_margin": round(gross_margin, 2),
                "expenses": {
                    "by_category": [{"key": k, "label": EXPENSE_CATEGORY_LABELS.get(k, k), "amount": round(v, 2)} for k, v in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)],
                    "total": round(total_expenses, 2),
                },
                "ebit_before_commissions": round(ebt, 2),
                "commissions": round(comm_total, 2),
                "net_profit": round(net, 2),
                "net_margin_pct": round(net / total_income * 100, 1) if total_income > 0 else 0,
            }

        return {
            "period": {"from": d_from, "to": d_to},
            "previous_period": {"from": prev_from, "to": prev_to},
            "current": compute(d_from, d_to),
            "previous": compute(prev_from, prev_to),
        }
    except Exception as e:
        logger.error(f"P&L report error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/reports/inventory")
async def inventory_report(
    branch_id: str = "", days_no_movement: int = 60,
    ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    require_finance_role(ctx)
    try:
        from datetime import datetime as dt, timedelta
        # 1. Valoración de inventario (cost + retail) por sucursal y categoría
        stock_q = sdb.table('inventory_stock').select('product_id,branch_id,quantity').eq('clinic_id', clinic_id)
        if branch_id: stock_q = stock_q.eq('branch_id', branch_id)
        stocks = stock_q.execute().data or []
        prod_ids = list({s['product_id'] for s in stocks})
        prods = {}
        if prod_ids:
            for pid in prod_ids:
                p = sdb.table('products').select('id,name,sku,cost_price,sale_price,category_id,min_stock').eq('id', pid).maybe_single().execute()
                p_data = getattr(p, 'data', None) if p else None
                if p_data: prods[pid] = p_data
        cost_total = 0.0
        retail_total = 0.0
        by_branch = {}
        by_category = {}
        for s in stocks:
            qty = float(s.get('quantity') or 0)
            if qty <= 0: continue
            p = prods.get(s['product_id'])
            if not p: continue
            cost = qty * float(p.get('cost_price') or 0)
            retail = qty * float(p.get('sale_price') or 0)
            cost_total += cost; retail_total += retail
            by_branch[s['branch_id']] = by_branch.get(s['branch_id'], {"cost": 0, "retail": 0})
            by_branch[s['branch_id']]['cost'] += cost; by_branch[s['branch_id']]['retail'] += retail
            cid = p.get('category_id') or 'none'
            by_category[cid] = by_category.get(cid, {"cost": 0, "retail": 0, "items": 0})
            by_category[cid]['cost'] += cost; by_category[cid]['retail'] += retail; by_category[cid]['items'] += int(qty)
        branch_arr = []
        for bid, v in by_branch.items():
            br = sdb.table('branches').select('name').eq('id', bid).maybe_single().execute()
            br_data = getattr(br, 'data', None) if br else None
            branch_arr.append({"branch_id": bid, "branch_name": br_data['name'] if br_data else '', "cost": round(v['cost'], 2), "retail": round(v['retail'], 2)})
        category_arr = []
        for cid, v in by_category.items():
            if cid == 'none':
                cat_name = 'Sin categoría'
            else:
                cat = sdb.table('product_categories').select('name').eq('id', cid).maybe_single().execute()
                cat_data = getattr(cat, 'data', None) if cat else None
                cat_name = cat_data['name'] if cat_data else 'Categoría'
            category_arr.append({"category": cat_name, "cost": round(v['cost'], 2), "retail": round(v['retail'], 2), "items": v['items']})
        category_arr.sort(key=lambda x: x['cost'], reverse=True)

        # 2. Productos sin movimiento (con stock pero sin venta en N días)
        cutoff = (dt.now(timezone.utc) - timedelta(days=days_no_movement)).isoformat()
        # Get products with active stock
        active_pids = [s['product_id'] for s in stocks if float(s.get('quantity') or 0) > 0]
        recently_sold = set()
        if active_pids:
            # batch in chunks of 50
            for i in range(0, len(active_pids), 50):
                chunk = active_pids[i:i+50]
                mvs = sdb.table('inventory_movements').select('product_id').eq('clinic_id', clinic_id).eq('movement_type', 'sale').in_('product_id', chunk).gte('created_at', cutoff).execute().data or []
                for m in mvs: recently_sold.add(m['product_id'])
        no_movement = []
        for pid in active_pids:
            if pid in recently_sold: continue
            p = prods.get(pid)
            if not p: continue
            qty = sum(float(s.get('quantity') or 0) for s in stocks if s['product_id'] == pid)
            no_movement.append({"id": pid, "name": p.get('name'), "sku": p.get('sku'), "quantity": qty, "value_cost": round(qty * float(p.get('cost_price') or 0), 2)})
        no_movement.sort(key=lambda x: x['value_cost'], reverse=True)

        # 3. Top 20 más vendidos (últimos 90 días)
        cutoff_90 = (dt.now(timezone.utc) - timedelta(days=90)).isoformat()
        all_sales = sdb.table('sales').select('id').eq('clinic_id', clinic_id).neq('status', 'cancelled').gte('created_at', cutoff_90)
        if branch_id: all_sales = all_sales.eq('branch_id', branch_id)
        recent_sale_ids = [s['id'] for s in (all_sales.execute().data or [])]
        top_sold = []
        if recent_sale_ids:
            top_totals = {}
            top_qty = {}
            # batch
            for i in range(0, len(recent_sale_ids), 50):
                chunk = recent_sale_ids[i:i+50]
                its = sdb.table('sale_items').select('product_id,quantity,total').in_('sale_id', chunk).not_.is_('product_id', 'null').execute().data or []
                for it in its:
                    pid = it.get('product_id')
                    if not pid: continue
                    top_totals[pid] = top_totals.get(pid, 0) + float(it.get('total') or 0)
                    top_qty[pid] = top_qty.get(pid, 0) + float(it.get('quantity') or 0)
            for pid, amount in top_totals.items():
                p = prods.get(pid)
                if not p:
                    pp = sdb.table('products').select('name,sku').eq('id', pid).maybe_single().execute()
                    p = getattr(pp, 'data', None) if pp else None
                if not p: continue
                top_sold.append({"id": pid, "name": p.get('name'), "sku": p.get('sku'), "quantity": top_qty.get(pid, 0), "amount": round(amount, 2)})
            top_sold.sort(key=lambda x: x['amount'], reverse=True)
            top_sold = top_sold[:20]

        # 4. Próximos a vencer
        expiring_resp = supabase_admin.table('v_expiring_products').select('*').eq('clinic_id', clinic_id).execute()
        expiring = expiring_resp.data or []

        # 5. Movimientos del período (últimos 30 días)
        cutoff_30 = (dt.now(timezone.utc) - timedelta(days=30)).isoformat()
        mvs = sdb.table('inventory_movements').select('movement_type,quantity').eq('clinic_id', clinic_id).gte('created_at', cutoff_30).execute().data or []
        movements_summary = {}
        for m in mvs:
            t = m.get('movement_type') or 'other'
            qty = float(m.get('quantity') or 0)
            if t not in movements_summary:
                movements_summary[t] = {"count": 0, "total_quantity": 0}
            movements_summary[t]['count'] += 1
            movements_summary[t]['total_quantity'] += qty

        return {
            "valuation": {
                "cost_total": round(cost_total, 2),
                "retail_total": round(retail_total, 2),
                "potential_margin": round(retail_total - cost_total, 2),
                "by_branch": branch_arr,
                "by_category": category_arr,
            },
            "no_movement_days": days_no_movement,
            "no_movement_products": no_movement[:50],
            "top_sold_90d": top_sold,
            "expiring": expiring[:20],
            "movements_30d": movements_summary,
        }
    except Exception as e:
        logger.error(f"Inventory report error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/reports/by-branch")
async def by_branch_report(
    period: str = "current_month", date_from: str = "", date_to: str = "",
    ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    require_finance_role(ctx)
    try:
        d_from, d_to = _period_dates(period, date_from, date_to)
        branches = sdb.table('branches').select('id,name').eq('clinic_id', clinic_id).eq('is_active', True).execute().data or []
        result = []
        for br in branches:
            sales = sdb.table('sales').select('total').eq('clinic_id', clinic_id).eq('branch_id', br['id']).neq('status', 'cancelled').gte('created_at', d_from).lte('created_at', d_to + 'T23:59:59Z').execute().data or []
            income = sum(float(s.get('total') or 0) for s in sales)
            exps = sdb.table('expenses').select('total').eq('clinic_id', clinic_id).eq('branch_id', br['id']).gte('expense_date', d_from).lte('expense_date', d_to).execute().data or []
            expenses_total = sum(float(e.get('total') or 0) for e in exps)
            apps = 0
            try:
                a = sdb.table('appointments').select('id', count='exact').eq('clinic_id', clinic_id).eq('branch_id', br['id']).gte('starts_at', d_from).lte('starts_at', d_to + 'T23:59:59Z').execute()
                apps = a.count or 0
            except Exception:
                pass
            avg_ticket = (income / len(sales)) if sales else 0
            result.append({
                "branch_id": br['id'], "branch_name": br['name'],
                "income": round(income, 2), "expenses": round(expenses_total, 2),
                "profit": round(income - expenses_total, 2),
                "sales_count": len(sales), "appointments": apps,
                "avg_ticket": round(avg_ticket, 2),
            })
        result.sort(key=lambda x: x['income'], reverse=True)
        totals = {
            "income": round(sum(r['income'] for r in result), 2),
            "expenses": round(sum(r['expenses'] for r in result), 2),
            "profit": round(sum(r['profit'] for r in result), 2),
            "sales_count": sum(r['sales_count'] for r in result),
            "appointments": sum(r['appointments'] for r in result),
        }
        return {"period": {"from": d_from, "to": d_to}, "branches": result, "totals": totals}
    except Exception as e:
        logger.error(f"By branch report error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/reports/pnl-pdf")
async def pnl_pdf(
    period: str = "current_month", date_from: str = "", date_to: str = "",
    branch_id: str = "", ctx=Depends(require_clinic_member)
):
    """Export P&L to PDF."""
    clinic_id = ctx["member"]["clinic_id"]
    require_finance_role(ctx)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import io
        from datetime import datetime as dt

        # Reuse calculation
        d_from, d_to = _period_dates(period, date_from, date_to)
        prev_from, prev_to = _previous_period(d_from, d_to)
        # Inline call to compute P&L (replicated structure)
        pnl_data = await pnl_report(period, date_from, date_to, branch_id, ctx=ctx)
        cur = pnl_data["current"]; prev = pnl_data["previous"]
        clinic = sdb.table('clinics').select('name,address,city,phone,email').eq('id', clinic_id).single().execute().data
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=18*mm, bottomMargin=18*mm, leftMargin=18*mm, rightMargin=18*mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='ClinicName3', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F1A2E')))
        styles.add(ParagraphStyle(name='Title3', fontSize=13, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488')))
        styles.add(ParagraphStyle(name='Sub3', fontSize=9, alignment=TA_CENTER, textColor=colors.grey))
        styles.add(ParagraphStyle(name='Sec3', fontSize=10, fontName='Helvetica-Bold', spaceBefore=4, spaceAfter=2))
        elements = []
        elements.append(Paragraph(clinic.get('name', 'Clínica'), styles['ClinicName3']))
        elements.append(Paragraph("Estado de Resultados (P&L)", styles['Title3']))
        elements.append(Paragraph(f"Período actual: {d_from} a {d_to} | Anterior: {prev_from} a {prev_to}", styles['Sub3']))
        elements.append(Spacer(1, 4*mm))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
        elements.append(Spacer(1, 4*mm))

        rows = [['Concepto', 'Actual', 'Anterior']]
        rows.append(['INGRESOS', '', ''])
        rows.append(['  Servicios médicos', f"Q{cur['income']['services']:.2f}", f"Q{prev['income']['services']:.2f}"])
        rows.append(['  Productos', f"Q{cur['income']['products']:.2f}", f"Q{prev['income']['products']:.2f}"])
        rows.append(['  TOTAL INGRESOS', f"Q{cur['income']['total']:.2f}", f"Q{prev['income']['total']:.2f}"])
        rows.append(['COSTO DE VENTAS', f"-Q{cur['cogs']:.2f}", f"-Q{prev['cogs']:.2f}"])
        rows.append(['MARGEN BRUTO', f"Q{cur['gross_margin']:.2f}", f"Q{prev['gross_margin']:.2f}"])
        rows.append(['GASTOS OPERATIVOS', '', ''])
        for c in cur['expenses']['by_category']:
            prev_c = next((x for x in prev['expenses']['by_category'] if x['key'] == c['key']), {'amount': 0})
            rows.append([f"  {c['label']}", f"-Q{c['amount']:.2f}", f"-Q{prev_c['amount']:.2f}"])
        rows.append(['  TOTAL GASTOS', f"-Q{cur['expenses']['total']:.2f}", f"-Q{prev['expenses']['total']:.2f}"])
        rows.append(['UTILIDAD ANTES COMISIONES', f"Q{cur['ebit_before_commissions']:.2f}", f"Q{prev['ebit_before_commissions']:.2f}"])
        rows.append(['COMISIONES MÉDICOS', f"-Q{cur['commissions']:.2f}", f"-Q{prev['commissions']:.2f}"])
        rows.append(['UTILIDAD NETA', f"Q{cur['net_profit']:.2f}", f"Q{prev['net_profit']:.2f}"])
        rows.append(['MARGEN NETO', f"{cur['net_margin_pct']}%", f"{prev['net_margin_pct']}%"])

        table = RLTable(rows, colWidths=[280, 110, 110])
        table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F1A2E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            # Bold for section headers and totals
            ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),
            ('FONTNAME', (0, 4), (-1, 4), 'Helvetica-Bold'),
            ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),
            ('FONTNAME', (0, 7), (0, 7), 'Helvetica-Bold'),
            ('FONTNAME', (0, -5), (-1, -5), 'Helvetica-Bold'),
            ('FONTNAME', (0, -3), (-1, -3), 'Helvetica-Bold'),
            ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, -2), (-1, -2), colors.HexColor('#0D9488')),
            ('FONTSIZE', (0, -2), (-1, -2), 11),
            ('LINEABOVE', (0, -2), (-1, -2), 1, colors.HexColor('#0D9488')),
        ]))
        elements.append(table)
        doc.build(elements)
        pdf_bytes = buf.getvalue()
        buf.close()

        path = f"{clinic_id}/reports/pnl_{d_from}_{d_to}_{int(dt.now(timezone.utc).timestamp())}.pdf"
        supabase_admin.storage.from_('patient-files').upload(path, pdf_bytes, {"content-type": "application/pdf", "upsert": "true"})
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        return {"url": signed.get('signedURL') or signed.get('signedUrl', '')}
    except Exception as e:
        logger.error(f"P&L PDF error: {e}")
        raise HTTPException(status_code=500, detail="Error")


