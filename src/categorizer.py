class Categorizer:
    def __init__(self, categories: list[dict], overrides: dict[str, str] | None = None):
        self.rules = []
        for cat in categories:
            name = cat["name"]
            for keyword in cat.get("keywords", []):
                self.rules.append((keyword.lower(), name))
            if not cat.get("keywords"):
                self.default_category = name
        if not hasattr(self, "default_category"):
            self.default_category = "Other"
        self.overrides = overrides or {}

    def categorize(self, merchant: str) -> tuple[str, str]:
        if not merchant:
            return (self.default_category, "default")
        merchant_lower = merchant.lower()
        for m, cat in self.overrides.items():
            if m.lower() in merchant_lower:
                return (cat, "learned")
        for keyword, category in self.rules:
            if keyword in merchant_lower:
                return (category, f"keyword:{keyword}")
        return (self.default_category, "default")

    def reload_overrides(self, overrides: dict) -> None:
        self.overrides = overrides

    def learn_merchant(self, merchant: str, category: str, storage=None) -> None:
        """Update in-memory overrides and optionally persist to storage."""
        self.overrides[merchant] = category
        if storage is not None:
            storage.set_merchant_override(merchant, category)
            self.overrides = storage.get_merchant_overrides()
