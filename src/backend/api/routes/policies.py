from fastapi import APIRouter, HTTPException, status

from src.backend.schemas.policy import PolicyCatalogDTO, PolicySourceDTO
from src.backend.services.policy_service import PolicyService

router = APIRouter(prefix="/policies", tags=["policies"])
service = PolicyService()


@router.get("/current", response_model=PolicyCatalogDTO)
async def current_policy() -> PolicyCatalogDTO:
    return PolicyCatalogDTO(**service.current())


@router.get("/current/source", response_model=PolicySourceDTO)
async def current_policy_source() -> PolicySourceDTO:
    try:
        content = service.source_text()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="POLICY_SOURCE_UNAVAILABLE"
        ) from exc
    return PolicySourceDTO(
        catalog_version=service.catalog.catalog_version,
        sha256=service.catalog.source_sha256,
        attribution=service.catalog.source_attribution,
        legal_notice=service.catalog.legal_notice,
        content=content,
    )
