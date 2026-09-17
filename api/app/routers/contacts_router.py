# Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
# Licensed under the MIT License. See LICENSE file in project root for details.

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.db import get_db
from app.models import ContactMapping

router = APIRouter(prefix="/contacts", dependencies=[Depends(verify_api_key)])


class ContactMappingCreate(BaseModel):
    display_name: str
    thread_id: str
    platform: Optional[str] = None


class ContactMappingOut(BaseModel):
    id: int
    display_name: str
    thread_id: str
    platform: str | None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[ContactMappingOut])
def list_mappings(db: Session = Depends(get_db)):
    return db.query(ContactMapping).all()


@router.post("/", response_model=ContactMappingOut, status_code=201)
def create_mapping(payload: ContactMappingCreate, db: Session = Depends(get_db)):
    mapping = ContactMapping(**payload.model_dump())
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/{mapping_id}")
def delete_mapping(mapping_id: int, db: Session = Depends(get_db)):
    mapping = db.query(ContactMapping).get(mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    db.delete(mapping)
    db.commit()
    return {"deleted": True}
