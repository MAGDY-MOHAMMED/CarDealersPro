from typing import Dict, List, Any

# 1. تصنيفات المركبات المتاحة في النظام
VEHICLE_CATEGORIES: List[str] = [
    "car", 
    "motorcycle", 
    "truck", 
    "van", 
    "bus", 
    "suv", 
    "pickup"
]

# 2. إعدادات البنوك الافتراضية (Global Defaults)
# دي القيم اللي السيستم بيلجأ ليها لو البنك محددش قيم خاصة بيه
FINANCE_CONFIG: Dict[str, Any] = {
    "default_interest_rates": {
        "new": 12.5,
        "used": 15.5
    },
    "default_min_down_payment": {
        "new": 15.0, # 15%
        "used": 30.0  # 30%
    },
    "max_tenure_months": {
        "new": 84,    # 7 سنوات
        "used": 60     # 5 سنوات
    },
    "income_debt_ratio": 0.40 # قاعدة الـ 40% من الدخل
}

# 3. أنواع القروض المدعومة
LOAN_TYPES: List[str] = ["New Car", "Used Car", "Refinance", "Corporate Loan"]

# 4. العملات المدعومة
SUPPORTED_CURRENCIES: List[str] = ["EGP", "USD", "EUR"]

# 5. تخصصات الفاحصين (للموديول القادم)
INSPECTOR_SPECIALIZATIONS: List[str] = [
    "Mechanic",  #
    "Body & Frame", 
    "Electrical", #
    "Interior & Detailing", 
    "Transmission & Drivetrain", 
    "Suspension Mechanic" #
]
default_categories = VEHICLE_CATEGORIES