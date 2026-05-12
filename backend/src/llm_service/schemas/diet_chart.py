from pydantic import BaseModel


class MealCellSchema(BaseModel):
    food: str
    timing: str


class DietChartGridSchema(BaseModel):
    meal_slots: list[str]
    grid: dict[str, dict[str, MealCellSchema]]

    def to_parameters(self, template_params: dict) -> dict:
        return {
            "is_template": False,
            "template_key": template_params.get("template_key", ""),
            "meal_slots": self.meal_slots,
            "grid": {
                day: {
                    slot: {"food": cell.food, "timing": cell.timing}
                    for slot, cell in slots.items()
                }
                for day, slots in self.grid.items()
            },
        }
