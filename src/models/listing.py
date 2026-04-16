from dataclasses import dataclass


@dataclass
class Listing:
    id: str
    title: str
    price: str
    location: str
    url: str
