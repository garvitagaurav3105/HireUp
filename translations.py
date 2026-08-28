"""Interface translations for HireUp.

Only the HireUp interface (labels, buttons, headings) is translated here.
Job data returned by the Adzuna API is always shown in its original language.
"""

LANGUAGES = {
    "en": "English",
    "hi": "हिन्दी",
}

DEFAULT_LANGUAGE = "en"

TRANSLATIONS = {
    "en": {
        "nav_language": "Language",
        "lang_apply": "Go",
        "home_tagline": "Your Password for a Successful Job",
        "home_intro": (
            "HireUp helps students discover job and internship opportunities "
            "across India. Pick your field, choose a city, and start exploring "
            "real openings."
        ),
        "field_profession": "Profession",
        "field_location": "Location",
        "field_location_ph": "Enter an Indian city (e.g. Mumbai)",
        "btn_search": "Search",
        "err_no_profession": "Please choose a profession.",
        "err_no_location": "Please enter a location.",
        "results_back": "New search",
        "results_found": "opportunities found",
        "company_unlisted": "Company not listed",
        "job_view": "View Opportunity",
        "page_word": "Page",
        "page_prev": "Previous",
        "page_next": "Next",
        "empty_title": "No opportunities found",
        "empty_body": (
            "We couldn't find any matching opportunities. "
            "Try a different profession or city."
        ),
        "error_retry": "Try again",
        "read_aloud": "Read results aloud",
        "read_stop": "Stop reading",
        "tab_results": "Results",
        "detail_back": "Back to results",
        "detail_back_home": "Back to search",
        "detail_category": "Category",
        "detail_contract_type": "Contract type",
        "detail_contract_time": "Contract time",
        "detail_salary": "Salary",
        "detail_description": "Description",
        "detail_view_original": "View original job listing",
        "detail_unavailable": "This opportunity is not available.",
        "footer_text": "A student project to help students find work.",
    },
    "hi": {
        "nav_language": "भाषा",
        "lang_apply": "जाएँ",
        "home_tagline": "सफल नौकरी के लिए आपका पासवर्ड",
        "home_intro": (
            "HireUp छात्रों को पूरे भारत में नौकरी और इंटर्नशिप के अवसर खोजने में "
            "मदद करता है। अपना क्षेत्र और शहर चुनें और वास्तविक अवसर देखना शुरू करें।"
        ),
        "field_profession": "पेशा",
        "field_location": "स्थान",
        "field_location_ph": "कोई भारतीय शहर दर्ज करें (जैसे, मुंबई)",
        "btn_search": "खोजें",
        "err_no_profession": "कृपया एक पेशा चुनें।",
        "err_no_location": "कृपया एक स्थान दर्ज करें।",
        "results_back": "नई खोज",
        "results_found": "अवसर मिले",
        "company_unlisted": "कंपनी दर्ज नहीं है",
        "job_view": "अवसर देखें",
        "page_word": "पृष्ठ",
        "page_prev": "पिछला",
        "page_next": "अगला",
        "empty_title": "कोई अवसर नहीं मिला",
        "empty_body": (
            "हमें कोई मिलता-जुलता अवसर नहीं मिला। "
            "कोई दूसरा पेशा या शहर आज़माएँ।"
        ),
        "error_retry": "पुनः प्रयास करें",
        "read_aloud": "परिणाम सुनें",
        "read_stop": "पढ़ना रोकें",
        "tab_results": "परिणाम",
        "detail_back": "परिणामों पर वापस",
        "detail_back_home": "खोज पर वापस",
        "detail_category": "श्रेणी",
        "detail_contract_type": "अनुबंध का प्रकार",
        "detail_contract_time": "अनुबंध की अवधि",
        "detail_salary": "वेतन",
        "detail_description": "विवरण",
        "detail_view_original": "मूल नौकरी सूची देखें",
        "detail_unavailable": "यह अवसर उपलब्ध नहीं है।",
        "footer_text": "छात्रों को काम ढूँढने में मदद करने वाला एक छात्र प्रोजेक्ट।",
    },
}
