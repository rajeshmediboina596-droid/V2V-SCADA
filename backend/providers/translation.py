import re
import json
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional
from backend.providers.base import TranslationProvider

# Canonical ISO-639-1 / BCP-47 registry for Supported Indian Languages
INDIAN_LANGUAGES = {
    "te": {"name": "Telugu", "native": "తెలుగు", "bcp47": "te-IN", "script": "Telugu"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "bcp47": "hi-IN", "script": "Devanagari"},
    "ta": {"name": "Tamil", "native": "தமிழ்", "bcp47": "ta-IN", "script": "Tamil"},
    "kn": {"name": "Kannada", "native": "ಕನ್ನಡ", "bcp47": "kn-IN", "script": "Kannada"},
    "ml": {"name": "Malayalam", "native": "മലയാളം", "bcp47": "ml-IN", "script": "Malayalam"},
    "mr": {"name": "Marathi", "native": "मराठी", "bcp47": "mr-IN", "script": "Devanagari"},
    "bn": {"name": "Bengali", "native": "বাংলা", "bcp47": "bn-IN", "script": "Bengali"},
    "gu": {"name": "Gujarati", "native": "ગુજરાતી", "bcp47": "gu-IN", "script": "Gujarati"},
    "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ", "bcp47": "pa-IN", "script": "Gurmukhi"},
    "or": {"name": "Odia", "native": "ଓଡ଼ିଆ", "bcp47": "or-IN", "script": "Odia"},
    "as": {"name": "Assamese", "native": "অসমীয়া", "bcp47": "as-IN", "script": "Bengali"},
    "en": {"name": "English", "native": "English", "bcp47": "en-IN", "script": "Latin"}
}

# Unicode Script Ranges for Auto-Language Detection
SCRIPT_RANGES = {
    "te": (0x0C00, 0x0C7F),  # Telugu
    "ta": (0x0B80, 0x0BFF),  # Tamil
    "kn": (0x0C80, 0x0CFF),  # Kannada
    "ml": (0x0D00, 0x0D7F),  # Malayalam
    "gu": (0x0A80, 0x0AFF),  # Gujarati
    "pa": (0x0A00, 0x0A7F),  # Gurmukhi / Punjabi
    "or": (0x0B00, 0x0B7F),  # Odia
    "devanagari": (0x0900, 0x097F),  # Hindi / Marathi
    "bengali_script": (0x0980, 0x09FF),  # Bengali / Assamese
}

# Offline Highway Emergency Lexicon covering all 12 Indian Languages
EMERGENCY_LEXICON = {
    "accident": {
        "te": "రోడ్డు ప్రమాదం జరిగింది, అత్యవసర సహాయం పంపండి.",
        "hi": "सड़क दुर्घटना हुई है, तत्काल आपातकालीन सहायता भेजें।",
        "ta": "சாலை விபத்து ஏற்பட்டுள்ளது, உடனடியாக அவசர உதவி அனுப்பவும்.",
        "kn": "ರಸ್ತೆ ಅಪಘಾತ ಸಂಭವಿಸಿದೆ, ತಕ್ಷಣ ತುರ್ತು ನೆರವು ಕಳುಹಿಸಿ.",
        "ml": "റോഡപകടം ഉണ്ടായിരിക്കുന്നു, അടിയന്തര സഹായം ഉടൻ അയക്കുക.",
        "mr": "रस्ता अपघात झाला आहे, तातडीने मदत पाठवावी.",
        "bn": "সড়ক দুর্ঘটনা ঘটেছে, অবিলম্বে জরুরি সাহায্য পাঠান।",
        "gu": "માર્ગ અકસ્માત થયો છે, તાત્કાલિક ઇમરજન્સી સહાય મોકલો.",
        "pa": "ਸੜਕ ਹਾਦਸਾ ਵਾਪਰਿਆ ਹੈ, ਤੁਰੰਤ ਐਮਰਜੈਂਸੀ ਸਹਾਇਤਾ ਭੇਜੋ।",
        "or": "ସଡ଼କ ଦୁର୍ଘଟଣା ଘଟିଛି, ତୁରନ୍ତ ଜରୁରୀ ସହାୟତା ପଠାନ୍ତୁ।",
        "as": "পথ দুৰ্ঘটনা ঘটিছে, অনতিপলমে জৰুৰী সাহায্য পঠিয়াওক।",
        "en": "Road accident occurred, dispatch emergency assistance immediately."
    },
    "ambulance": {
        "te": "తీవ్ర గాయాలయ్యాయి, వెంటనే అంబులెన్స్ కావాలి.",
        "hi": "गंभीर चोटें आई हैं, तुरंत एम्बुलेंस चाहिए।",
        "ta": "கடுமையான காயம் ஏற்பட்டுள்ளது, உடனடியாக ஆம்புலன்ஸ் வேண்டும்.",
        "kn": "ತೀವ್ರ ಗಾಯಗಳಾಗಿವೆ, ಕೂಡಲೇ ಆಂಬ್ಯುಲೆನ್ಸ್ ಕಳುಹಿಸಿ.",
        "ml": "ഗുരുതരമായി പരിക്കേറ്റവരുണ്ട്, ഉടൻ ആംബുലൻസ് വേണം.",
        "mr": "गंभीर दुखापत झाली आहे, त्वरित रुग्णवाहिका पाठवा.",
        "bn": "গুরুতর আঘাত লেগেছে, অবিলম্বে অ্যাম্বুলেন্স প্রয়োজন।",
        "gu": "ગંભીર ઈજાઓ થઈ છે, તાત્કાલિક એમ્બ્યુલન્સ જોઈએ છે.",
        "pa": "ਗੰਭੀਰ ਸੱਟਾਂ ਲੱਗੀਆਂ ਹਨ, ਤੁਰੰਤ ਐਂਬੂਲੈਂਸ ਦੀ ਲੋੜ ਹੈ।",
        "or": "ଗୁରୁତର ଆଘାତ ଲାଗିଛି, ତୁରନ୍ତ ଆମ୍ବୁଲାନ୍ସ ଆବଶ୍ୟକ।",
        "as": "গুৰুতৰ আঘাত পাইছে, তৎক্ষণাৎ এম্বুলেন্সৰ প্ৰয়োজন।",
        "en": "Severe injuries reported, need an ambulance immediately."
    },
    "brake_failure": {
        "te": "బ్రేక్ విఫలమైంది! చుట్టుపక్కల వాహనాలు దయచేసి పక్కకు వెళ్లండి.",
        "hi": "ब्रेक फेल हो गया है! कृपया आसपास के वाहन रास्ता दें।",
        "ta": "பிரேக் செயல் இழந்தது! சுற்றியுள்ள வாகனங்கள் விலகிச் செல்லவும்.",
        "kn": "ಬ್ರೇಕ್ ವಿಫಲವಾಗಿದೆ! ದಯವಿಟ್ಟು ಇತರ ವಾಹನಗಳು ದಾರಿ ಬಿಡಿ.",
        "ml": "ബ്രേക്ക് തകരാറിലായി! ചുറ്റുമുള്ള വാഹനങ്ങൾ വഴിമാറുക.",
        "mr": "ब्रेक निकामी झाले आहेत! कृपया सभोवतालच्या वाहनांनी बाजूला व्हा.",
        "bn": "ব্রেক ফেইল করেছে! আশেপাশের যানবাহন অনুগ্রহ করে পথ দিন।",
        "gu": "બ્રેક ફેલ થઈ ગઈ છે! આસપાસના વાહનો કૃપા કરીને બાજુ પર ખસો.",
        "pa": "ਬ੍ਰੇਕ ਫੇਲ੍ਹ ਹੋ ਗਈ ਹੈ! ਕਿਰਪਾ ਕਰਕੇ ਆਸ-ਪਾਸ ਦੇ ਵਾਹਨ ਰਸਤਾ ਦੇਣ।",
        "or": "ବ୍ରେକ୍ ଫେଲ୍ ହୋଇଯାଇଛି! ଆଖପାଖର ଯାନବାହନ ଦୟାକରି ରାସ୍ତା ଛାଡନ୍ତୁ।",
        "as": "ব্ৰেক বিকল হৈছে! ওচৰৰ যান-বাহনে দয়া কৰি পথ এৰি দিয়ক।",
        "en": "Brake failure detected! Surrounding vehicles please clear the way."
    },
    "toll_assistance": {
        "te": "టోల్‌గేట్ వద్ద సమస్య ఉంది, ఆపరేటర్ సహాయం కావాలి.",
        "hi": "टोल प्लाजा पर समस्या है, ऑपरेटर से बात करनी है।",
        "ta": "சுங்கச்சாவடியில் சிக்கல் உள்ளது, ஆபரேட்டர் உதவி தேவை.",
        "kn": "ಟೋಲ್ ಗೇಟ್ ಬಳಿ ಸಮಸ್ಯೆಯಾಗಿದೆ, ಆಪರೇಟರ್ ನೆರವು ಬೇಕು.",
        "ml": "ടോൾ പ്ലാസയിൽ പ്രശ്നമുണ്ട്, ഓപ്പറേറ്ററുടെ സഹായം വേണം.",
        "mr": "टोल नाक्यावर अडचण आहे, ऑपरेटरची मदत हवी आहे.",
        "bn": "টোল প্লাজায় সমস্যা হয়েছে, অপারেটরের সাহায্য প্রয়োজন।",
        "gu": "ટોલ પ્લાઝા પર મુશ્કેલી છે, ઓપરેટરની સહાય જોઈએ છે.",
        "pa": "ਟੋਲ ਪਲਾਜ਼ਾ 'ਤੇ ਸਮੱਸਿਆ ਹੈ, ਆਪਰੇਟਰ ਦੀ ਸਹਾਇਤਾ ਚਾਹੀਦੀ ਹੈ।",
        "or": "ଟୋଲ୍ ପ୍ଲାଜାରେ ସମସ୍ୟା ଅଛି, ଅପରେଟରଙ୍କ ସହାୟତା ଦରକାର।",
        "as": "টোল প্লাজাত সমস্যা হৈছে, অপাৰেটৰৰ সহায় লাগিব।",
        "en": "Issue at toll plaza, operator assistance requested."
    },
    "flat_tire": {
        "te": "టైరు పంక్చర్ అయింది, హైవే పెట్రోల్ సహాయం కావాలి.",
        "hi": "टायर पंक्चर हो गया है, हाईवे पेट्रोल सहायता चाहिए।",
        "ta": "டயர் பஞ்சராகிவிட்டது, நெடுஞ்சாலை ரோந்து உதவி தேவை.",
        "kn": "ಟೈರ್ ಪಂಕ್ಚರ್ ಆಗಿದೆ, ಹೆದ್ದಾರಿ ಗಸ್ತು ಸಿಬ್ಬಂದಿ ಸಹಾಯ ಬೇಕು.",
        "ml": "ടയർ പഞ്ചറായി, ഹൈവേ പട്രോൾ സഹായം വേണം.",
        "mr": "टायर पंक्चर झाला आहे, हायवे पेट्रोलची मदत हवी आहे.",
        "bn": "টায়ার পাংচার হয়েছে, হাইওয়ে পেট্রোল সহায়তা প্রয়োজন।",
        "gu": "ટાયર પંચર થઈ ગયું છે, હાઇવે પેટ્રોલ સહાય જોઈએ છે.",
        "pa": "ਟਾਇਰ ਪੰਕਚਰ ਹੋ ਗਿਆ ਹੈ, ਹਾਈਵੇ ਪੈਟਰੋਲ ਦੀ ਮਦਦ ਚਾਹੀਦੀ ਹੈ।",
        "or": "ଟାୟାର ପଙ୍କଚର ହୋଇଯାଇଛି, ହାଇୱେ ପେଟ୍ରୋଲ ସହାୟତା ଦରକାର।",
        "as": "টায়াৰ পাংচাৰ হৈছে, হাইৱে পেট্ৰ’লৰ সহায় লাগে।",
        "en": "Flat tire reported, requesting highway patrol support."
    },
    "fire_hazard": {
        "te": "వాహనంలో మంటలు చెలరేగాయి! వెంటనే ఫైర్ ఇంజిన్ పంపండి.",
        "hi": "गाड़ी में आग लग गई है! कृपया तुरंत दमकल गाड़ी भेजें।",
        "ta": "வாகனத்தில் தீ பிடித்துள்ளது! உடனடியாக தீயணைப்பு வாகனம் அனுப்பவும்.",
        "kn": "ವಾಹನದಲ್ಲಿ ಬೆಂಕಿ ಕಾಣಿಸಿಕೊಂಡಿದೆ! ತಕ್ಷಣ ಅಗ್ನಿಶಾಮಕ ದಳ ಕಳುಹಿಸಿ.",
        "ml": "വാഹനത്തിൽ തീപിടുത്തമുണ്ടായി! ഉടൻ ഫയർ എഞ്ചിൻ അയക്കുക.",
        "mr": "गाडीला आग लागली आहे! कृपया तातडीने अग्निशामक दल पाठवा.",
        "bn": "গাড়িতে আগুন লেগেছে! অবিলম্বে ফায়ার সার্ভিস পাঠান।",
        "gu": "વાહનમાં આગ લાગી છે! કૃપા કરીને તાત્કાલિક ફાયર બ્રિગેડ મોકલો.",
        "pa": "ਗੱਡੀ ਨੂੰ ਅੱਗ ਲੱਗ ਗਈ ਹੈ! ਕਿਰਪਾ ਕਰਕੇ ਤੁਰੰਤ ਫਾਇਰ ਬ੍ਰਿਗੇਡ ਭੇਜੋ।",
        "or": "ଗାଡ଼ିରେ ନିଆଁ ଲାଗିଯାଇଛି! ଦୟାକରି ତୁରନ୍ତ ଦମକଳ ପଠାନ୍ତୁ।",
        "as": "গাড়ীত জুই লাগিছে! অতি শীঘ্ৰে অগ্নিনিৰ্বাপক বাহিনী পঠিয়াওক।",
        "en": "Vehicle fire hazard! Dispatch fire rescue immediately."
    },
    "fuel_empty": {
        "te": "ఇంధనం అయిపోయింది, హైవే పై వాహనం నిలిచిపోయింది.",
        "hi": "ईंधन खत्म हो गया है, गाड़ी हाईवे पर रुक गई है।",
        "ta": "எரிபொருள் தீர்ந்துவிட்டது, நெடுஞ்சாலையில் வாகனம் நின்றுவிட்டது.",
        "kn": "ಇಂಧನ ಖಾಲಿಯಾಗಿದೆ, ವಾಹನ ಹೆದ್ದಾರಿಯಲ್ಲಿ ನಿಂತಿದೆ.",
        "ml": "ഇന്ധനം തീർന്നു, വാഹനം ഹൈവേയിൽ നിന്നുപോയി.",
        "mr": "इंधन संपले आहे, गाडी महामार्गावर बंद पडली आहे.",
        "bn": "জ্বালানি শেষ হয়ে গেছে, হাইওয়েতে গাড়ি থেমে গেছে।",
        "gu": "ઈંધણ પૂરું થઈ ગયું છે, વાહન હાઇવે પર અટકી ગયું છે.",
        "pa": "ਤੇਲ ਖਤਮ ਹੋ ਗਿਆ ਹੈ, ਗੱਡੀ ਹਾਈਵੇ 'ਤੇ ਖੜ੍ਹ ਗਈ ਹੈ।",
        "or": "ଇନ୍ଧନ ସରିଯାଇଛି, ଗାଡ଼ି ରାଜପଥରେ ଅଟକି ଯାଇଛି।",
        "as": "ইন্ধন শেষ হ'ল, বাহনখন হাইৱেত ৰৈ গৈছে।",
        "en": "Fuel exhausted, vehicle stranded on the highway."
    },
    "wrong_way": {
        "te": "హెచ్చరిక: ఎదురుగా తప్పు దిశలో వాహనం వస్తోంది.",
        "hi": "चेतावनी: सामने गलत दिशा से वाहन आ रहा है।",
        "ta": "எச்சரிக்கை: தவறான திசையில் வாகனம் எதிரே வருகிறது.",
        "kn": "ಎಚ್ಚರಿಕೆ: ತಪ್ಪು ದಿಕ್ಕಿನಲ್ಲಿ ವಾಹನ ಎದುರಿಗೆ ಬರುತ್ತಿದೆ.",
        "ml": "മുന്നറിയിപ്പ്: തെറ്റായ ദിശയിൽ വാഹനം വരുന്നു.",
        "mr": "इशारा: चुकीच्या दिशेने समोरून वाहन येत आहे.",
        "bn": "সতর্কতা: ভুল দিক থেকে গাড়ি আসছে।",
        "gu": "ચેતવણી: ખોટી દિશામાંથી વાહન સામે આવી રહ્યું છે.",
        "pa": "ਚੇਤਾਵਨੀ: ਗਲਤ ਦਿਸ਼ਾ ਤੋਂ ਵਾਹਨ ਆ ਰਿਹਾ ਹੈ।",
        "or": "ଚେତାବନୀ: ଭୁଲ ଦିଗରୁ ସାମ୍ନାରେ ଗାଡ଼ି ଆସୁଛି।",
        "as": "সতৰ্কবাণী: ভুল দিশৰ পৰা বাহন আহি আছে।",
        "en": "Warning: Wrong-way vehicle approaching ahead."
    },
    "yield_emergency": {
        "te": "అత్యవసర రెస్క్యూ వాహనం వస్తోంది, వెంటనే మార్గం ఇవ్వండి.",
        "hi": "आपातकालीन वाहन आ रहा है, तुरंत रास्ता साफ करें।",
        "ta": "அவசர மீட்பு வாகனம் வருகிறது, உடனடியாக வழி விடவும்.",
        "kn": "ತುರ್ತು ರಕ್ಷಣಾ ವಾಹನ ಬರುತ್ತಿದೆ, ಕೂಡಲೇ ಮಾರ್ಗ ಬಿಟ್ಟುಕೊಡಿ.",
        "ml": "അടിയന്തര വാഹനം വരുന്നു, ഉടൻ വഴി നൽകുക.",
        "mr": "आपत्कालीन वाहन येत आहे, त्वरित रस्ता मोकळा करा.",
        "bn": "জরুরি রেসকিউ যান আসছে, অবিলম্বে রাস্তা ছেড়ে দিন।",
        "gu": "ઇમરજન્સી વાહન આવી રહ્યું છે, તાત્કાલિક રસ્તો આપો.",
        "pa": "ਐਮਰਜੈਂਸੀ ਵਾਹਨ ਆ ਰਿਹਾ ਹੈ, ਤੁਰੰਤ ਰਸਤਾ ਦਿਓ।",
        "or": "ଜରୁରୀକାଳୀନ ଯାନ ଆସୁଛି, ତୁରନ୍ତ ରାସ୍ତା ଛାଡିଦିଅନ୍ତୁ।",
        "as": "জৰুৰীকালীন বাহন আহি আছে, সোনকালে পথ এৰি দিয়ক।",
        "en": "Emergency vehicle approaching, yield right of way immediately."
    },
    "tow_truck": {
        "te": "వాహనం బ్రేక్‌డౌన్ అయింది, టోవింగ్ వ్యాన్ పంపండి.",
        "hi": "गाड़ी खराब हो गई है, टोइंग वैन की आवश्यकता है।",
        "ta": "வாகனம் பழுதாகிவிட்டது, டோவிங் வாகனம் தேவை.",
        "kn": "ವಾಹನ ಕೆಟ್ಟಿದೆ, ಟೋಯಿಂಗ್ ವಾಹನ ಕಳುಹಿಸಿ.",
        "ml": "വാഹനം കേടായി, ടോവിംഗ് വാൻ വേണം.",
        "mr": "गाडी नादुरुस्त झाली आहे, टोइंग व्हॅन पाठवा.",
        "bn": "গাড়ি নষ্ট হয়ে গেছে, টোয়িং ভ্যান পাঠানো হোক।",
        "gu": "વાહન બગડી ગયું છે, ટોઇંગ વાનની જરૂર છે.",
        "pa": "ਗੱਡੀ ਖਰਾਬ ਹੋ ਗਈ ਹੈ, ਟੋਇੰਗ ਵੈਨ ਦੀ ਲੋੜ ਹੈ।",
        "or": "ଗାଡ଼ି ଖରାପ ହୋଇଯାଇଛି, ଟୋଇଂ ଭ୍ୟାନ୍ ଦରକାର।",
        "as": "গাড়ী বিকল হৈছে, টোয়িং ভেনৰ প্ৰয়োজন।",
        "en": "Vehicle breakdown, dispatch a towing vehicle."
    }
}

class MultiIndianTranslationEngine(TranslationProvider):
    """
    Continuous Multi-Indian-Language Translation Engine.
    Operates without hardcoded pairwise logic:
    Source Language -> Auto Detect -> Offline Lexicon / Neural API -> Target Language.
    """

    def __init__(self, mode: str = "hybrid"):
        self.mode = mode
        self.supported_langs = INDIAN_LANGUAGES

    def get_supported_languages(self) -> Dict[str, str]:
        return {code: f"{data['name']} ({data['native']})" for code, data in self.supported_langs.items()}

    def register_language(self, code: str, name: str, native: str, bcp47: str, script: str):
        """Allows adding new Indian languages dynamically without core code rewrite."""
        self.supported_langs[code] = {
            "name": name,
            "native": native,
            "bcp47": bcp47,
            "script": script
        }

    async def detect_language(self, text: str) -> str:
        """
        Fast Unicode script block detector + linguistic stopword analyzer.
        Identifies any of the 12 Indian languages or English accurately.
        """
        if not text or not text.strip():
            return "en"

        text_stripped = text.strip()

        # Count character script distributions
        counts = {lang: 0 for lang in SCRIPT_RANGES}
        ascii_count = 0

        for char in text_stripped:
            code_pt = ord(char)
            if 0x0020 <= code_pt <= 0x007E:
                ascii_count += 1
                continue
            for script_key, (low, high) in SCRIPT_RANGES.items():
                if low <= code_pt <= high:
                    counts[script_key] += 1
                    break

        # Check dominant Indic script
        dominant_script = max(counts, key=counts.get)
        if counts[dominant_script] > 0:
            if dominant_script == "devanagari":
                # Distinguish Marathi from Hindi using characteristic markers
                marathi_markers = ["आहे", "झाला", "करतो", "नाही", "होते", "आणि", "कसे", "मला"]
                if any(m in text_stripped for m in marathi_markers):
                    return "mr"
                return "hi"
            elif dominant_script == "bengali_script":
                # Distinguish Assamese from Bengali (e.g. 'ৰ' U+09F0, 'ৱ' U+09F1)
                if "\u09f0" in text_stripped or "\u09f1" in text_stripped:
                    return "as"
                return "bn"
            else:
                return dominant_script

        # Fallback to English if ASCII dominated
        return "en"

    def _match_lexicon(self, text: str, target_lang: str) -> Optional[str]:
        """Checks if text contains an emergency highway concept in any language."""
        text_lower = text.lower()

        # Direct concept key check
        for concept, translations in EMERGENCY_LEXICON.items():
            if concept in text_lower:
                return translations.get(target_lang)
            for lang_code, phrase in translations.items():
                if phrase.lower() in text_lower or text_lower in phrase.lower():
                    return translations.get(target_lang)

        # Keyword root matcher across all 12 Indian languages
        KEYWORD_ROOTS = {
            "accident": ["ప్రమాదం", "दुर्घटना", "விபத்து", "ಅಪಘಾತ", "अपघात", "দুর্ঘটনা", "અકસ્માત", "ਹਾਦਸਾ", "ଦୁର୍ଘଟଣା", "দুৰ্ঘটনা", "accident", "crash", "collision"],
            "ambulance": ["అంబులెన్స్", "గాయ", "एम्बुलेंस", "चोट", "ஆம்புலன்ஸ்", "காயம்", "ಆಂಬ್ಯುಲೆನ್ಸ್", "ಗಾಯ", "रुग्णवाहिका", "अ্যাম্বুলেন্স", "એમ્બ્યુલન્સ", "ਐਂਬੂਲੈਂਸ", "ଆମ୍ବୁଲାନ୍ସ", "এম্বুলেন্স", "ambulance", "injury", "hospital"],
            "brake_failure": ["బ్రేక్", "ब्रेक", "பிரேக்", "ಬ್ರೇಕ್", "ব্রেক", "બ્રેક", "ਬ੍ਰੇਕ", "ବ୍ରେକ୍", "ব্ৰেক", "brake"],
            "toll_assistance": ["టోల్", "టోల్‌గేట్", "टोल", "सुங்க", "ಟೋಲ್", "টোল", "ટોલ", "ਟੋਲ", "ଟୋଲ୍", "toll", "plaza"],
            "flat_tire": ["టైరు", "పంక్చర్", "टायर", "पंचर", "டயர்", "பஞ்சர்", "ಟೈರ್", "ಪಂಕ್ಚರ್", "টায়ার", "ટાયર", "ਟਾਇਰ", "ଟାୟାର", "টায়াৰ", "puncture", "flat tire"],
            "fire_hazard": ["మంటలు", "ఆగ", "आग", "दमकल", "தீ", "ಬೆಂಕಿ", "আগুন", "આગ", "ਅੱਗ", "ନିଆଁ", "জুই", "fire", "smoke"],
            "fuel_empty": ["ఇంధనం", "ईंधन", "எரிபொருள்", "ಇಂಧನ", "इंधन", "জ্বালানি", "ઈંધણ", "ਤੇਲ", "ଇନ୍ଧନ", "ইন্ধন", "fuel", "gas", "petrol", "diesel"],
            "wrong_way": ["తప్పు దిశ", "गलत दिशा", "தவறான திசை", "ತಪ್ಪು ದಿಕ್ಕು", "चुकीच्या", "ভুল দিক", "ખોટી દિશા", "ਗਲਤ ਦਿਸ਼ਾ", "ଭୁଲ ଦିଗ", "ভুল দিশ", "wrong way"],
            "yield_emergency": ["మార్గం ఇవ్వండి", "రాస్తా", "मार्ग", "दಾರಿ ಬಿಡಿ", "রাস্তা", "পথ", "yield", "siren"],
            "tow_truck": ["టోవింగ్", "టోయింగ్", "टोइंग", "டோவிங்", "ಟೋಯಿಂಗ್", "টোয়িং", "ટોઇંગ", "ਟੋਇੰਗ", "ଟୋଇଂ", "টোয়িং", "towing", "breakdown"]
        }

        for concept, kws in KEYWORD_ROOTS.items():
            if any(kw in text_lower for kw in kws):
                return EMERGENCY_LEXICON.get(concept, {}).get(target_lang)

        return None

    def _neural_translate_online(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        Standard library HTTP request to Google / Indic API.
        1.5 second timeout ensures low latency during conversational voice streaming.
        """
        try:
            params = urllib.parse.urlencode({
                "client": "gtx",
                "sl": source_lang,
                "tl": target_lang,
                "dt": "t",
                "q": text
            })
            url = f"https://translate.googleapis.com/translate_a/single?{params}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "V2V-SCADA-VoiceEngine/2.0 (MoRTH AIS-230)"}
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    raw_data = resp.read().decode("utf-8")
                    result = json.loads(raw_data)
                    translated = "".join([segment[0] for segment in result[0] if segment and segment[0]])
                    if translated and translated.strip():
                        return translated.strip()
        except Exception:
            pass
        return None

    async def translate(self, text: str, source_lang: str, target_lang: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes continuous translation pipeline:
        1. Auto-detect source language if 'auto'
        2. Check for identical languages
        3. Tier 1: Offline Automotive Emergency Lexicon (100% internet-independent)
        4. Tier 2: Online Neural Indic Translator (1.5s bounded latency)
        5. Tier 3: Offline Resilient Fallback (Never crashes SCADA!)
        """
        clean_text = text.strip() if text else ""
        if not clean_text:
            return {
                "source_lang": source_lang,
                "detected_lang": source_lang,
                "target_lang": target_lang,
                "original_text": "",
                "translated_text": "",
                "confidence": 1.0,
                "engine": "Empty"
            }

        # Auto-detect language if requested or unspecified
        detected_lang = source_lang
        if source_lang == "auto" or not source_lang:
            detected_lang = await self.detect_language(clean_text)
            source_lang = detected_lang

        # Direct identity
        if source_lang == target_lang:
            return {
                "source_lang": source_lang,
                "detected_lang": detected_lang,
                "target_lang": target_lang,
                "original_text": clean_text,
                "translated_text": clean_text,
                "confidence": 1.0,
                "engine": "Identity (Same Language)"
            }

        # Tier 1: Offline Emergency Lexicon match
        if self.mode in ("hybrid", "lexicon_only"):
            lexicon_match = self._match_lexicon(clean_text, target_lang)
            if lexicon_match:
                return {
                    "source_lang": source_lang,
                    "detected_lang": detected_lang,
                    "target_lang": target_lang,
                    "original_text": clean_text,
                    "translated_text": lexicon_match,
                    "confidence": 0.98,
                    "engine": "Offline Indic Lexicon (Instant)"
                }

        # Tier 2: Online Neural Indic Translator
        if self.mode in ("hybrid", "online_only"):
            neural_res = self._neural_translate_online(clean_text, source_lang, target_lang)
            if neural_res:
                return {
                    "source_lang": source_lang,
                    "detected_lang": detected_lang,
                    "target_lang": target_lang,
                    "original_text": clean_text,
                    "translated_text": neural_res,
                    "confidence": 0.94,
                    "engine": "Neural Indic Engine"
                }

        # Tier 3: Offline Graceful Fallback
        src_name = self.supported_langs.get(source_lang, {}).get("name", source_lang.upper())
        tgt_name = self.supported_langs.get(target_lang, {}).get("name", target_lang.upper())
        fallback_text = f"[{src_name} → {tgt_name}]: {clean_text}"

        return {
            "source_lang": source_lang,
            "detected_lang": detected_lang,
            "target_lang": target_lang,
            "original_text": clean_text,
            "translated_text": fallback_text,
            "confidence": 0.65,
            "engine": "Offline Emergency Fallback"
        }
