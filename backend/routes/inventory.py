"""Auto-extracted from server.py — DO NOT EDIT MANUALLY without checking server.py."""
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

router = APIRouter()

from server import sdb, supabase_admin, require_clinic_member, now_iso, logger

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
        new_qty = data["new_quantity"]
        reason = data.get("reason", "adjustment")
        notes = data.get("notes", "")
        existing_res = sdb.table('inventory_stock').select('id,quantity').eq('product_id', product_id).eq('branch_id', branch_id).maybe_single().execute()
        existing = getattr(existing_res, 'data', None) if existing_res else None
        old_qty = existing['quantity'] if existing else 0
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

