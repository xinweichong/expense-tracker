class Categorizer:
    def __init__(self, categories: list[dict]):
        self.rules = []
        for cat in categories:
            name = cat["name"]
            for keyword in cat.get("keywords", []):
                self.rules.append((keyword.lower(), name))
            if not cat.get("keywords"):
                self.default_category = name

        if not hasattr(self, "default_category"):
            self.default_category = "Other"

    def categorize(self, merchant: str) -> str:
        if not merchant:
            return self.default_category
        merchant_lower = merchant.lower()
        for keyword, category in self.rules:
            if keyword in merchant_lower:
                return category
        return self.default_category
