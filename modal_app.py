import json
import os

import modal


image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("agent","tools","products","product_store","order_store","message_service","instagram_channel")
    .add_local_dir("frontend", "/root/frontend")
)

app = modal.App("mini-agent")
secret = modal.Secret.from_name("openrouter-secret")
product_volume = modal.Volume.from_name("mini-agent-data", create_if_missing=True)

@app.function(image=image,secrets=[secret],volumes={"/data":product_volume})
@modal.asgi_app()
def web():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse
    web_app=FastAPI()

    @web_app.get("/")
    async def home(): return FileResponse("/root/frontend/index.html")
    @web_app.get("/admin")
    async def admin(): return FileResponse("/root/frontend/admin.html")
    @web_app.get("/admin/dashboard-page")
    async def dashboard_page(): return FileResponse("/root/frontend/dashboard.html")

    def require_admin(request):
        import hmac
        expected=os.environ.get("ADMIN_PASSWORD","")
        if not expected or not hmac.compare_digest(request.headers.get("x-admin-password",""),expected):
            raise HTTPException(status_code=401,detail="رمز مدیریت نادرست است.")

    @web_app.get("/admin/dashboard")
    async def dashboard(request:Request):
        require_admin(request)
        product_volume.reload()
        from order_store import load_orders
        orders=load_orders()
        confirmed=[o for o in orders if o.get("status") in ("confirmed","shipped")]
        cancelled=[o for o in orders if o.get("status")=="cancelled"]
        top={}
        for o in confirmed:
            name=o.get("product_name","")
            top[name]=top.get(name,0)+int(o.get("quantity",0))
        return {"orders":{"total":len(orders),"pending":sum(o.get("status")=="pending" for o in orders),"confirmed":len(confirmed)},"sales":{"confirmed_amount":sum(o.get("total_price",0) for o in confirmed),"cancelled_amount":sum(o.get("total_price",0) for o in cancelled)},"top_products":[{"name":k,"quantity":v} for k,v in sorted(top.items(),key=lambda x:x[1],reverse=True)[:5]]}

    @web_app.get("/style.css")
    async def style(): return FileResponse("/root/frontend/style.css")
    return web_app
