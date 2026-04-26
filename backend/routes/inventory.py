"""Auto-extracted from server.py — DO NOT EDIT MANUALLY without checking server.py."""
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

router = APIRouter()

from core import sdb, supabase_admin, require_clinic_member, require_clinic_admin, now_iso, logger

# ============== INVENTORY ROUTES ==============

# --- Product Categories ---
@router.get("/clinic/inventory/categories")
async def list_product_categories(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('product_categories').select('*').eq('clinic_id', clinic_id).order('sort_order').order('name').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List categories error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/inventory/categories")
async def create_product_category(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        doc = {"id": str(uuid.uuid4()), "clinic_id": clinic_id, "name": data["name"],
               "description": data.get("description"), "parent_id": data.get("parent_id"),
               "is_active": True, "sort_order": data.get("sort_order", 0)}
        sdb.table('product_categories').insert(doc).execute()
        return {"id": doc["id"], "message": "Categoría creada"}
    except Exception as e:
        logger.error(f"Create category error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Products ---
@router.get("/clinic/inventory/products")
async def list_products(q: str = "", category_id: str = "", low_stock: str = "", page: int = 1, limit: int = 20, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('products').select('*', count='exact').eq('clinic_id', clinic_id)
        if q:
            query = query.or_(f'name.ilike.%{q}%,sku.ilike.%{q}%,barcode.ilike.%{q}%')
        if category_id:
            query = query.eq('category_id', category_id)
        offset = (page - 1) * limit
        result = query.order('name').range(offset, offset + limit - 1).execute()
        products = result.data or []
        for p in products:
            stock = sdb.table('inventory_stock').select('quantity,branch_id').eq('product_id', p['id']).execute()
            p['total_stock'] = sum(s.get('quantity', 0) for s in (stock.data or []))
            p.pop('search_vector', None)
            if p.get('category_id'):
                cat = sdb.table('product_categories').select('name').eq('id', p['category_id']).maybe_single().execute()
                cat_data = getattr(cat, 'data', None) if cat else None
                p['category_name'] = cat_data['name'] if cat_data else ''
            else:
                p['category_name'] = ''
        if low_stock == 'true':
            products = [p for p in products if p['total_stock'] <= (p.get('min_stock') or 0)]
        return {"products": products, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List products error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/inventory/products")
async def create_product(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        doc = {
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "sku": data.get("sku"), "barcode": data.get("barcode"), "name": data["name"],
            "description": data.get("description"), "brand": data.get("brand"),
            "presentation": data.get("presentation"), "category_id": data.get("category_id"),
            "medication_id": data.get("medication_id"),
            "cost_price": data.get("cost_price", 0), "sale_price": data.get("sale_price", 0),
            "tax_rate": data.get("tax_rate", 12), "unit": data.get("unit", "unidad"),
            "min_stock": data.get("min_stock", 0), "max_stock": data.get("max_stock"),
            "requires_prescription": data.get("requires_prescription", False),
            "has_expiration": data.get("has_expiration", False),
            "is_active": data.get("is_active", True),
        }
        sdb.table('products').insert(doc).execute()
        return {"id": doc["id"], "message": "Producto creado"}
    except Exception as e:
        logger.error(f"Create product error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.put("/clinic/inventory/products/{product_id}")
async def update_product(product_id: str, data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        allowed = ['sku','barcode','name','description','brand','presentation','category_id','medication_id','cost_price','sale_price','tax_rate','unit','min_stock','max_stock','requires_prescription','has_expiration','is_active']
        update = {k: v for k, v in data.items() if k in allowed}
        update['updated_at'] = now_iso()
        sdb.table('products').update(update).eq('id', product_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Producto actualizado"}
    except Exception as e:
        logger.error(f"Update product error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/inventory/products/search")
async def search_products(q: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('products').select('id,name,sku,brand,sale_price,cost_price,has_expiration').eq('clinic_id', clinic_id).eq('is_active', True)
        if q and len(q) >= 2:
            query = query.or_(f'name.ilike.%{q}%,sku.ilike.%{q}%')
        result = query.order('name').limit(20).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Search products error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Stock ---
@router.get("/clinic/inventory/stock")
async def list_stock(branch_id: str = "", category_id: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('inventory_stock').select('*').eq('clinic_id', clinic_id)
        if branch_id:
            query = query.eq('branch_id', branch_id)
        result = query.execute()
        stocks = result.data or []
        for s in stocks:
            p = sdb.table('products').select('name,sku,min_stock,category_id').eq('id', s['product_id']).maybe_single().execute()
            p_data = getattr(p, 'data', None) if p else None
            if p_data:
                s['product_name'] = p_data['name']
                s['sku'] = p_data['sku']
                s['min_stock'] = p_data.get('min_stock', 0)
                s['category_id'] = p_data.get('category_id')
            else:
                s['product_name'] = '?'
                s['sku'] = ''
                s['min_stock'] = 0
            b = sdb.table('branches').select('name').eq('id', s['branch_id']).maybe_single().execute()
            b_data = getattr(b, 'data', None) if b else None
            s['branch_name'] = b_data['name'] if b_data else ''
            qty = s.get('quantity', 0)
            ms = s.get('min_stock', 0)
            s['status'] = 'critical' if qty <= 0 else ('low' if qty <= ms else 'ok')
        if category_id:
            stocks = [s for s in stocks if s.get('category_id') == category_id]
        return stocks
    except Exception as e:
        logger.error(f"List stock error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/inventory/alerts")
async def get_inventory_alerts(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        low_stock = []
        expiring = []
        # Low stock: products where any branch has qty <= min_stock
        products = sdb.table('products').select('id,name,sku,min_stock').eq('clinic_id', clinic_id).eq('is_active', True).execute()
        for p in (products.data or []):
            stocks = sdb.table('inventory_stock').select('quantity,branch_id').eq('product_id', p['id']).execute()
            for s in (stocks.data or []):
                if s.get('quantity', 0) <= (p.get('min_stock') or 0):
                    b = sdb.table('branches').select('name').eq('id', s['branch_id']).maybe_single().execute()
                    b_data = getattr(b, 'data', None) if b else None
                    low_stock.append({**p, "quantity": s['quantity'], "branch_id": s['branch_id'], "branch_name": b_data['name'] if b_data else ''})
        # Expiring: batches expiring in 60 days
        from datetime import datetime as dt, timedelta
        cutoff = (dt.now(timezone.utc) + timedelta(days=60)).isoformat()
        batches = sdb.table('inventory_batches').select('*').eq('clinic_id', clinic_id).eq('is_active', True).lt('expiration_date', cutoff).order('expiration_date').limit(20).execute()
        for b in (batches.data or []):
            p = sdb.table('products').select('name,sku').eq('id', b['product_id']).maybe_single().execute()
            p_data = getattr(p, 'data', None) if p else None
            br = sdb.table('branches').select('name').eq('id', b['branch_id']).maybe_single().execute()
            br_data = getattr(br, 'data', None) if br else None
            expiring.append({**b, "product_name": p_data['name'] if p_data else '', "sku": p_data['sku'] if p_data else '', "branch_name": br_data['name'] if br_data else ''})
        return {"low_stock": low_stock, "expiring": expiring}
    except Exception as e:
        logger.error(f"Inventory alerts error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/inventory/adjust")
async def adjust_stock(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        product_id = data["product_id"]
        branch_id = data["branch_id"]
        new_qty = int(data["new_quantity"])
        reason = data.get("reason", "adjustment")
        notes = data.get("notes", "")
        existing_res = sdb.table('inventory_stock').select('id,quantity').eq('product_id', product_id).eq('branch_id', branch_id).maybe_single().execute()
        existing = getattr(existing_res, 'data', None) if existing_res else None
        old_qty = int(existing['quantity']) if existing else 0
        diff = new_qty - old_qty
        # Insert only the movement; a Postgres trigger on inventory_movements
        # automatically upserts inventory_stock by summing quantities.
        sdb.table('inventory_movements').insert({
            "id": str(uuid.uuid4()), "clinic_id": clinic_id, "product_id": product_id,
            "branch_id": branch_id, "movement_type": "adjustment", "quantity": diff,
            "notes": f"{reason}: {notes}".strip(': '), "performed_by": member["id"],
            "created_at": now_iso(),
        }).execute()
        return {"message": "Stock ajustado", "old": old_qty, "new": new_qty, "diff": diff}
    except Exception as e:
        logger.error(f"Adjust stock error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Movements ---
@router.get("/clinic/inventory/movements")
async def list_movements(product_id: str = "", branch_id: str = "", movement_type: str = "", date_from: str = "", date_to: str = "", page: int = 1, limit: int = 30, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('inventory_movements').select('*', count='exact').eq('clinic_id', clinic_id)
        if product_id: query = query.eq('product_id', product_id)
        if branch_id: query = query.eq('branch_id', branch_id)
        if movement_type: query = query.eq('movement_type', movement_type)
        if date_from: query = query.gte('created_at', date_from)
        if date_to: query = query.lte('created_at', date_to + "T23:59:59Z")
        offset = (page - 1) * limit
        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        movements = result.data or []
        for m in movements:
            p = sdb.table('products').select('name,sku').eq('id', m['product_id']).maybe_single().execute()
            p_data = getattr(p, 'data', None) if p else None
            m['product_name'] = p_data['name'] if p_data else ''
            m['sku'] = p_data.get('sku', '') if p_data else ''
            b = sdb.table('branches').select('name').eq('id', m['branch_id']).maybe_single().execute()
            b_data = getattr(b, 'data', None) if b else None
            m['branch_name'] = b_data['name'] if b_data else ''
            if m.get('performed_by'):
                mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', m['performed_by']).maybe_single().execute()
                mb_data = getattr(mb, 'data', None) if mb else None
                m['performed_by_name'] = f"{mb_data['first_name']} {mb_data['last_name']}" if mb_data else ''
            else:
                m['performed_by_name'] = ''
        return {"movements": movements, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List movements error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Suppliers ---
@router.get("/clinic/inventory/suppliers")
async def list_suppliers(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('suppliers').select('*').eq('clinic_id', clinic_id).order('name').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List suppliers error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/inventory/suppliers")
async def create_supplier(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        doc = {"id": str(uuid.uuid4()), "clinic_id": clinic_id, "name": data["name"],
               "tax_id": data.get("tax_id"), "contact_person": data.get("contact_person"),
               "phone": data.get("phone"), "email": data.get("email"),
               "address": data.get("address"), "notes": data.get("notes"), "is_active": True}
        sdb.table('suppliers').insert(doc).execute()
        return {"id": doc["id"], "message": "Proveedor creado"}
    except Exception as e:
        logger.error(f"Create supplier error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.put("/clinic/inventory/suppliers/{supplier_id}")
async def update_supplier(supplier_id: str, data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        allowed = ['name','tax_id','contact_person','phone','email','address','notes','is_active']
        update = {k: v for k, v in data.items() if k in allowed}
        sdb.table('suppliers').update(update).eq('id', supplier_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Proveedor actualizado"}
    except Exception as e:
        logger.error(f"Update supplier error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Purchase Orders ---
@router.get("/clinic/inventory/purchase-orders")
async def list_purchase_orders(status: str = "", page: int = 1, limit: int = 20, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('purchase_orders').select('*', count='exact').eq('clinic_id', clinic_id)
        if status: query = query.eq('status', status)
        offset = (page - 1) * limit
        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        orders = result.data or []
        for o in orders:
            b = sdb.table('branches').select('name').eq('id', o['branch_id']).maybe_single().execute()
            b_data = getattr(b, 'data', None) if b else None
            o['branch_name'] = b_data['name'] if b_data else ''
            items = sdb.table('purchase_order_items').select('id', count='exact').eq('purchase_order_id', o['id']).execute()
            o['item_count'] = items.count or 0
        return {"orders": orders, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List POs error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/inventory/purchase-orders")
async def create_purchase_order(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        now = now_iso()
        po_id = str(uuid.uuid4())
        items = data.get('items', [])
        subtotal = sum(i.get('subtotal', 0) for i in items)
        tax = subtotal * (data.get('tax_rate', 12) / 100)
        total = subtotal + tax
        status = data.get('status', 'pending')

        sdb.table('purchase_orders').insert({
            "id": po_id, "clinic_id": clinic_id, "branch_id": data["branch_id"],
            "order_number": data.get("order_number", f"PO-{now[:10]}"),
            "supplier_name": data.get("supplier_name", ""),
            "supplier_id": data.get("supplier_id"),
            "subtotal": subtotal, "tax_amount": tax, "total": total,
            "status": status, "notes": data.get("notes"),
            "created_by": member["id"], "created_at": now, "updated_at": now,
        }).execute()

        for item in items:
            sdb.table('purchase_order_items').insert({
                "id": str(uuid.uuid4()), "purchase_order_id": po_id,
                "product_id": item["product_id"], "quantity": item["quantity"],
                "unit_cost": item.get("unit_cost", 0),
                "subtotal": item.get("subtotal", item["quantity"] * item.get("unit_cost", 0)),
                "batch_number": item.get("batch_number"),
                "expiration_date": item.get("expiration_date"),
            }).execute()

        # If status is 'received', process stock entries
        if status == 'received':
            await process_po_receive(po_id, clinic_id, data["branch_id"], member["id"])

        return {"id": po_id, "message": "Orden creada"}
    except Exception as e:
        logger.error(f"Create PO error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

async def process_po_receive(po_id: str, clinic_id: str, branch_id: str, performed_by: str):
    """Process receiving a purchase order - insert movement (trigger updates stock) and create batches"""
    items = sdb.table('purchase_order_items').select('*').eq('purchase_order_id', po_id).execute()
    for item in (items.data or []):
        pid = item['product_id']
        qty = item['quantity']
        # Insert movement; Postgres trigger on inventory_movements upserts inventory_stock automatically.
        sdb.table('inventory_movements').insert({
            "id": str(uuid.uuid4()), "clinic_id": clinic_id, "product_id": pid,
            "branch_id": branch_id, "movement_type": "purchase",
            "quantity": qty, "unit_cost": item.get('unit_cost'),
            "reference_type": "purchase_order", "reference_id": po_id,
            "performed_by": performed_by, "created_at": now_iso(),
        }).execute()
        # Create batch if has expiration
        if item.get('expiration_date') or item.get('batch_number'):
            sdb.table('inventory_batches').insert({
                "id": str(uuid.uuid4()), "clinic_id": clinic_id, "product_id": pid,
                "branch_id": branch_id, "batch_number": item.get('batch_number', ''),
                "quantity": qty, "expiration_date": item.get('expiration_date'),
                "cost_price": item.get('unit_cost'), "received_at": now_iso(), "is_active": True,
            }).execute()
    # Mark PO as received
    sdb.table('purchase_orders').update({"status": "received", "received_at": now_iso(), "updated_at": now_iso()}).eq('id', po_id).execute()




# ============== BULK PRODUCT IMPORT (CSV / XLSX) ==============

PRODUCT_REQUIRED = ["name"]
PRODUCT_OPTIONAL = [
    "sku", "barcode", "description", "brand", "presentation", "category",
    "cost_price", "sale_price", "tax_rate", "unit",
    "min_stock", "max_stock", "requires_prescription", "has_expiration",
    "initial_stock",  # seeds inventory_stock for the active/main branch
]

def _parse_product_row(row: dict) -> dict:
    """Normalize a row dict into a Supabase-ready product document."""
    def s(field):
        v = row.get(field)
        if v is None:
            return ""
        if isinstance(v, (int, float)):
            # Avoid trailing .0 for ints
            if isinstance(v, float) and v.is_integer():
                return str(int(v)).strip()
            return str(v).strip()
        return str(v).strip()

    def num(field, default=0.0):
        raw = s(field)
        if not raw:
            return default
        try:
            return float(raw.replace(",", "."))
        except (ValueError, TypeError):
            return default

    def boolish(field, default=False):
        raw = s(field).lower()
        if not raw:
            return default
        return raw in ("1", "true", "yes", "y", "si", "sí", "verdadero")

    return {
        "name": s("name"),
        "sku": s("sku") or None,
        "barcode": s("barcode") or None,
        "description": s("description") or None,
        "brand": s("brand") or None,
        "presentation": s("presentation") or None,
        "_category_label": s("category") or None,  # resolved to category_id below
        "cost_price": num("cost_price"),
        "sale_price": num("sale_price"),
        "tax_rate": num("tax_rate", 12),
        "unit": s("unit") or "unidad",
        "min_stock": int(num("min_stock")),
        "max_stock": int(num("max_stock")) if s("max_stock") else None,
        "requires_prescription": boolish("requires_prescription"),
        "has_expiration": boolish("has_expiration"),
        "_initial_stock": num("initial_stock"),
    }

def _parse_xlsx_simple(raw: bytes) -> list:
    """Parse .xlsx into list of row dicts (mirrors patients._parse_xlsx)."""
    import io as _io
    from openpyxl import load_workbook
    wb = load_workbook(filename=_io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    headers = next(rows, None)
    if not headers:
        raise HTTPException(status_code=400, detail="XLSX sin encabezados")
    norm_headers = [(str(h or "").strip().lower().replace(" ", "_")) for h in headers]
    out = []
    for row in rows:
        if all(c is None or str(c).strip() == "" for c in row):
            continue
        out.append({norm_headers[i]: c for i, c in enumerate(row) if i < len(norm_headers)})
    return out

def _parse_csv_simple(raw: bytes) -> list:
    """Parse CSV bytes into list of row dicts (mirrors patients._parse_csv)."""
    import csv as _csv
    import io as _io
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise HTTPException(status_code=400, detail="No se pudo decodificar el CSV (use UTF-8)")
    sample = text[:2048]
    try:
        dialect = _csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except _csv.Error:
        dialect = _csv.excel
    reader = _csv.DictReader(_io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV sin encabezados")
    norm_headers = {h: (h or "").strip().lower().replace(" ", "_") for h in reader.fieldnames}
    out = []
    for r in reader:
        d = {norm_headers[k]: v for k, v in r.items() if k in norm_headers}
        # Skip phantom rows produced by trailing newlines / fully empty lines
        if not any((str(v).strip() if v is not None else "") for v in d.values()):
            continue
        out.append(d)
    return out

@router.post("/clinic/inventory-bulk/import")
async def import_products(
    file: UploadFile = File(...),
    branch_id: Optional[str] = None,
    commit: bool = False,
    ctx=Depends(require_clinic_admin),
):
    """Bulk-import products from a CSV or XLSX file.

    Required columns: name
    Optional: sku, barcode, description, brand, presentation, category, cost_price,
              sale_price, tax_rate, unit, min_stock, max_stock, requires_prescription,
              has_expiration, initial_stock

    Dedup: case-insensitive by sku (if provided) → fallback to name+brand
    initial_stock: when commit=true, seeds inventory_stock at the given branch_id
                   (or the clinic's main branch if not provided).
    """
    clinic_id = ctx["member"]["clinic_id"]
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo supera el límite de 5 MB")
    fname = (file.filename or "").lower()
    if fname.endswith(".xlsx"):
        rows = _parse_xlsx_simple(raw)
    elif fname.endswith(".csv"):
        rows = _parse_csv_simple(raw)
    else:
        raise HTTPException(status_code=400, detail="Formato no soportado (use .csv o .xlsx)")
    if not rows:
        raise HTTPException(status_code=400, detail="Archivo sin filas de datos")

    # Verify required headers exist
    sample_keys = set(rows[0].keys())
    missing = [r for r in PRODUCT_REQUIRED if r not in sample_keys]
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {', '.join(missing)}")

    # Resolve target branch for initial stock seeding (commit mode only)
    target_branch_id = branch_id
    if not target_branch_id:
        br = sdb.table('branches').select('id,is_main').eq('clinic_id', clinic_id).eq('is_active', True).execute()
        if br.data:
            main = next((b for b in br.data if b.get('is_main')), None)
            target_branch_id = (main or br.data[0])['id']

    # Pre-fetch existing products for dedup + categories
    existing = sdb.table('products').select('sku,name,brand').eq('clinic_id', clinic_id).execute()
    existing_sku = set()
    existing_composite = set()
    for p in (existing.data or []):
        if p.get('sku'):
            existing_sku.add(p['sku'].strip().lower())
        comp = f"{(p.get('name') or '').strip().lower()}|{(p.get('brand') or '').strip().lower()}"
        existing_composite.add(comp)

    cats = sdb.table('product_categories').select('id,name').eq('clinic_id', clinic_id).execute()
    cat_by_name = {(c.get('name') or '').strip().lower(): c['id'] for c in (cats.data or [])}

    valid_rows = []  # (product_doc, initial_stock)
    errors = []
    skipped_dup = 0
    preview = []
    new_categories_to_create = {}  # label_lower -> label

    for idx, raw_row in enumerate(rows, start=2):  # row 1 = header
        try:
            doc = _parse_product_row(raw_row)
            for req in PRODUCT_REQUIRED:
                if not str(doc.get(req) or "").strip():
                    errors.append({"row": idx, "field": req, "message": "Campo requerido vacío"})
                    raise ValueError("missing required")
            sku_lower = (doc.get("sku") or "").strip().lower()
            comp = f"{doc['name'].strip().lower()}|{(doc.get('brand') or '').strip().lower()}"
            if sku_lower and sku_lower in existing_sku:
                skipped_dup += 1
                continue
            if comp in existing_composite:
                skipped_dup += 1
                continue
            if sku_lower:
                existing_sku.add(sku_lower)
            existing_composite.add(comp)

            # Resolve / queue category creation
            cat_label = doc.pop("_category_label", None)
            initial_stock = doc.pop("_initial_stock", 0) or 0
            if cat_label:
                key = cat_label.strip().lower()
                if key in cat_by_name:
                    doc["category_id"] = cat_by_name[key]
                else:
                    new_categories_to_create[key] = cat_label
                    doc["category_id"] = None  # will be filled after creation

            doc["id"] = str(uuid.uuid4())
            doc["clinic_id"] = clinic_id
            doc["is_active"] = True
            valid_rows.append((doc, initial_stock, cat_label))
            if len(preview) < 5:
                preview.append({
                    "name": doc["name"],
                    "sku": doc.get("sku"),
                    "brand": doc.get("brand"),
                    "category": cat_label,
                    "sale_price": doc.get("sale_price"),
                    "initial_stock": initial_stock,
                })
        except ValueError:
            continue
        except Exception as e:
            errors.append({"row": idx, "field": "*", "message": str(e)[:120]})

    imported = 0
    stock_seeded = 0
    categories_created = 0
    commit_errors = []
    if commit and valid_rows:
        # First, create any missing categories so we can resolve category_id
        if new_categories_to_create:
            cat_docs = [
                {"id": str(uuid.uuid4()), "clinic_id": clinic_id, "name": label, "is_active": True}
                for label in new_categories_to_create.values()
            ]
            try:
                sdb.table('product_categories').insert(cat_docs).execute()
                categories_created = len(cat_docs)
                for c in cat_docs:
                    cat_by_name[c['name'].strip().lower()] = c['id']
            except Exception as e:
                commit_errors.append({"batch": 0, "message": f"Error al crear categorías: {str(e)[:160]}"})

        # Resolve any pending category_id references now that categories exist
        for tup in valid_rows:
            doc, _, cat_label = tup
            if cat_label and not doc.get("category_id"):
                doc["category_id"] = cat_by_name.get(cat_label.strip().lower())

        # Insert products in batches
        BATCH = 500
        product_docs = [d for d, _, _ in valid_rows]
        for i in range(0, len(product_docs), BATCH):
            chunk = product_docs[i:i + BATCH]
            try:
                sdb.table('products').insert(chunk).execute()
                imported += len(chunk)
            except Exception as e:
                commit_errors.append({"batch": i // BATCH + 1, "message": str(e)[:200]})

        # Seed inventory_stock for products with initial_stock > 0 at target branch
        if target_branch_id and not commit_errors:
            stock_docs = []
            for doc, initial, _ in valid_rows:
                if initial and float(initial) > 0:
                    stock_docs.append({
                        "id": str(uuid.uuid4()),
                        "clinic_id": clinic_id,
                        "branch_id": target_branch_id,
                        "product_id": doc["id"],
                        "quantity": int(float(initial)),
                    })
            if stock_docs:
                for i in range(0, len(stock_docs), BATCH):
                    chunk = stock_docs[i:i + BATCH]
                    try:
                        sdb.table('inventory_stock').insert(chunk).execute()
                        stock_seeded += len(chunk)
                    except Exception as e:
                        commit_errors.append({"batch": i // BATCH + 1, "message": f"Stock seed: {str(e)[:160]}"})

    return {
        "total": len(valid_rows) + len(errors) + skipped_dup,
        "valid_rows": len(valid_rows),
        "error_rows": len(errors),
        "duplicates_skipped": skipped_dup,
        "errors": errors[:50],
        "preview": preview,
        "imported": imported,
        "categories_created": categories_created,
        "stock_seeded": stock_seeded,
        "target_branch_id": target_branch_id,
        "committed": commit and not commit_errors,
        "commit_errors": commit_errors,
    }

@router.get("/clinic/inventory-bulk/template")
async def products_import_template(format: str = "csv", ctx=Depends(require_clinic_member)):
    """Download a CSV or XLSX template with required + optional product columns and one example row."""
    headers = PRODUCT_REQUIRED + PRODUCT_OPTIONAL
    example = {
        "name": "Acetaminofén 500mg",
        "sku": "MED-ACE-500",
        "barcode": "7501234567890",
        "brand": "Tylenol",
        "presentation": "Tableta",
        "category": "Analgésicos",
        "cost_price": 1.25,
        "sale_price": 2.50,
        "tax_rate": 12,
        "unit": "unidad",
        "min_stock": 20,
        "max_stock": 200,
        "requires_prescription": "false",
        "has_expiration": "true",
        "initial_stock": 50,
    }
    if format == "xlsx":
        from openpyxl import Workbook
        from fastapi.responses import StreamingResponse
        import io as _io
        wb = Workbook()
        ws = wb.active
        ws.title = "Productos"
        ws.append(headers)
        ws.append([example.get(h, "") for h in headers])
        buf = _io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="plantilla_productos.xlsx"'},
        )
    csv_text = ",".join(headers) + "\n" + ",".join(f'"{example.get(h, "")}"' for h in headers) + "\n"
    return {"filename": "plantilla_productos.csv", "headers": headers, "content": csv_text}
