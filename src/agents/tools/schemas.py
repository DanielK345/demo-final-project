from pydantic import BaseModel, Field


class SearchPlaceParams(BaseModel):
    query: str = Field(min_length=1)


class CreateBookingParams(BaseModel):
    pickup_place_id: str = Field(min_length=1)
    destination_place_id: str = Field(min_length=1)
    phone_number: str = Field(min_length=1)


class LookupTripParams(BaseModel):
    booking_id: str | None = None
    phone_number: str | None = None


class RetrieveKnowledgeParams(BaseModel):
    query: str = Field(min_length=1)


class CreateHandoffParams(BaseModel):
    session_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    context: dict = Field(default_factory=dict)

