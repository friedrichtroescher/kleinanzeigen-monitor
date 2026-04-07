from dataclasses import dataclass, field

@dataclass
class ListingDetail:
    description: str = ""
    shipping: str = ""
    attributes: dict[str, str] = field(default_factory=dict)