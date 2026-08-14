from enum import StrEnum


class VehicleType(StrEnum):
    MOTORBIKE = "MOTORBIKE"
    CAR_4 = "CAR_4"
    CAR_7 = "CAR_7"

    @property
    def spoken_label(self) -> str:
        return {
            type(self).MOTORBIKE: "xe máy",
            type(self).CAR_4: "ô tô 4 chỗ",
            type(self).CAR_7: "ô tô 7 chỗ",
        }[self]
