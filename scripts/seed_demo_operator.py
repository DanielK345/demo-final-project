"""Create a local development operator account without enabling role signup."""

from __future__ import annotations

import argparse
import asyncio

from src.backend.config import get_settings
from src.backend.repositories.persistence_repository import PersistenceRepository
from src.backend.services.auth_service import _hash_password
from src.backend.services.policy_service import PolicyService

DEMO_OPERATOR_PHONE = "0900000001"
DEMO_OPERATOR_PASSWORD = "Operator123!"


async def seed_demo_operator(
    *,
    phone: str = DEMO_OPERATOR_PHONE,
    password: str = DEMO_OPERATOR_PASSWORD,
    full_name: str = "Tổng đài viên AloSM (Demo)",
) -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise RuntimeError("Không seed tài khoản operator demo trong production")
    repository = PersistenceRepository()
    existing = await repository.user_by_phone(phone)
    if existing is not None:
        if existing.get("role") != "OPERATOR":
            raise RuntimeError("Số demo operator đã thuộc tài khoản khác; không tự đổi role")
        print(f"Operator đã tồn tại: {phone}")
        return
    catalog = PolicyService().catalog
    await repository.create_user(
        full_name=full_name,
        phone=phone,
        password_hash=_hash_password(password),
        terms_version=catalog.catalog_version,
        privacy_version=catalog.catalog_version,
        source_sha256=catalog.source_sha256,
        role="OPERATOR",
    )
    print(f"Đã tạo operator demo: {phone} / {password}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed a development-only AloSM operator")
    parser.add_argument("--phone", default=DEMO_OPERATOR_PHONE)
    parser.add_argument("--password", default=DEMO_OPERATOR_PASSWORD)
    parser.add_argument("--name", default="Tổng đài viên AloSM (Demo)")
    args = parser.parse_args()
    asyncio.run(seed_demo_operator(phone=args.phone, password=args.password, full_name=args.name))
