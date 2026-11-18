from typing import Literal, Optional
from pydantic import BaseModel, Field, computed_field

# 1. Fixed allowed categories so your charts stay clean
CategoryType = Literal[
    "groceries",
    "dining",
    "utilities",
    "university",
    "rent",
    "transport",
    "other",
]


# 2. Schema for each individual item printed on a receipt
class LineItem(BaseModel):
    name_ja: str = Field(description="Original Japanese item name as printed")
    name_en: str = Field(description="Concise English translation")
    price_jpy: int = Field(ge=0, description="Item price in Japanese Yen")


# 3. Main schema for the entire receipt or PDF document
class DocumentExtraction(BaseModel):
    document_type: Literal["receipt", "bill", "official_notice", "other"]
    vendor_or_issuer: str = Field(description="Store, utility company, or office name")
    date_iso: Optional[str] = Field(
        default=None, description="Date in YYYY-MM-DD format if visible"
    )
    items: list[LineItem] = Field(
        default_factory=list, description="Individual line items if this is a receipt"
    )
    tax_jpy: int = Field(
        default=0,
        ge=0,
        description="Separate consumption tax (外税) in JPY if not already inside item prices",
    )
    total_amount_jpy: int = Field(
        ge=0, description="Printed grand total in JPY (0 if non-financial notice)"
    )
    category: CategoryType
    english_summary: str = Field(
        description="2-sentence plain English summary of what this document is"
    )
    action_deadline: Optional[str] = Field(
        default=None, description="Payment or submission deadline if any"
    )

    # 4. Automated Math Sanity Check (Human-in-the-Loop flag)
    @computed_field
    @property
    def calculated_total_jpy(self) -> int:
        return sum(item.price_jpy for item in self.items) + self.tax_jpy

    @computed_field
    @property
    def needs_review(self) -> bool:
        # Only check math if individual line items were extracted
        if not self.items:
            return False
        return self.calculated_total_jpy != self.total_amount_jpy