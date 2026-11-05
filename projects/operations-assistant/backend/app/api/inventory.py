from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.dependencies import current_user
from app.repositories.inventory import get_inventory, list_stores
from app.schemas.auth import AuthContext

router = APIRouter(tags=["inventory"])


@router.get("/stores")
def stores(context: Annotated[AuthContext, Depends(current_user)]):
    return {"items": list_stores(context.account_codes)}


@router.get("/inventory/{msku}")
def inventory(
    msku: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    store_id: Annotated[str, Query(min_length=1, max_length=64, pattern=r"\S")],
    context: Annotated[AuthContext, Depends(current_user)],
):
    item = get_inventory(store_id.strip(), msku.strip(), context.account_codes)
    if item is None:
        raise HTTPException(status_code=404, detail="当前店铺下未找到该商品")
    return {"data_source": "authorized_test_snapshot", "inventory": item}
