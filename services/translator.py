"""
Namma Payana — Kannada Translator & Pronunciation Engine (v3.0)
Powered by Google Gemini AI for accurate, contextual Kannada translations.
Falls back to a verified lexicon (fast path) and then to MyMemory API.
"""

import re
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional

logger = logging.getLogger("nammapayana.translator")

# ─── Verified Lexicon (fast-path for common travel phrases) ───────────────────
# These are manually curated, culturally accurate Karnataka travel expressions.
VERIFIED_LEXICON = {
    # Greetings & Courtesies
    "hello": {"meaning": "Hello / Respectful greetings", "kn": "ನಮಸ್ಕಾರ", "tr": "Namaskara", "syllables": "Na-mas-kaa-ra", "tone": "Formal & Respectful", "context": "Universal respectful greeting in all situations across Karnataka."},
    "good morning": {"meaning": "Good morning", "kn": "ಶುಭೋದಯ", "tr": "Shubhōdaya", "syllables": "Shu-bho-da-ya", "tone": "Formal", "context": "Polite morning greeting."},
    "good evening": {"meaning": "Good evening", "kn": "ಶುಭ ಸಂಜೆ", "tr": "Shubha sanje", "syllables": "Shu-bha san-je", "tone": "Formal", "context": "Polite evening greeting."},
    "thank you": {"meaning": "Thank you", "kn": "ಧನ್ಯವಾದಗಳು", "tr": "Dhanyavadagalu", "syllables": "Dhan-ya-vaa-da-ga-lu", "tone": "Polite & Formal", "context": "Standard expression of sincere gratitude."},
    "thank you very much": {"meaning": "Thank you very much", "kn": "ತುಂಬಾ ಧನ್ಯವಾದಗಳು", "tr": "Tumba dhanyavadagalu", "syllables": "Tum-ba dhan-ya-vaa-da-ga-lu", "tone": "Warm & Polite", "context": "Expressing heartfelt gratitude to drivers, hosts, or locals."},
    "how are you": {"meaning": "How are you?", "kn": "ಹೇಗಿದ್ದೀರಾ?", "tr": "Hegiddeera?", "syllables": "Heg-id-dee-ra?", "tone": "Respectful", "context": "Polite inquiry to elders, shopkeepers, or new acquaintances."},
    "i am fine": {"meaning": "I am fine / doing well", "kn": "ನಾನು ಚೆನ್ನಾಗಿದ್ದೇನೆ", "tr": "Naanu chennagiddene", "syllables": "Naa-nu chen-naa-gid-de-ne", "tone": "Standard", "context": "Proper reply to 'Hegiddeera?'."},
    "what is your name": {"meaning": "What is your name?", "kn": "ನಿಮ್ಮ ಹೆಸರು ಏನು?", "tr": "Nimma hesaru enu?", "syllables": "Nim-ma he-sa-ru e-nu?", "tone": "Respectful", "context": "Polite way to ask someone's name."},
    "my name is": {"meaning": "My name is...", "kn": "ನನ್ನ ಹೆಸರು...", "tr": "Nanna hesaru...", "syllables": "Nan-na he-sa-ru...", "tone": "Standard", "context": "Introducing yourself in Kannada."},
    "please": {"meaning": "Please", "kn": "ದಯವಿಟ್ಟು", "tr": "Dayavittu", "syllables": "Da-ya-vit-tu", "tone": "Very Polite", "context": "Use before asking for a favor, ticket, or direction."},
    "sorry": {"meaning": "Sorry / Excuse me", "kn": "ಕ್ಷಮಿಸಿ", "tr": "Kshamisi", "syllables": "Ksha-mi-si", "tone": "Polite", "context": "Apologizing or excusing yourself in a crowd."},
    "yes": {"meaning": "Yes", "kn": "ಹೌದು", "tr": "Haudu", "syllables": "Hau-du", "tone": "Standard", "context": "Affirmative answer."},
    "no": {"meaning": "No", "kn": "ಇಲ್ಲ", "tr": "Illa", "syllables": "Il-la", "tone": "Standard", "context": "Negative answer."},

    # Transport & Auto Rickshaw
    "where is the bus stand": {"meaning": "Where is the bus stand?", "kn": "ಬಸ್ ನಿಲ್ದಾಣ ಎಲ್ಲಿದೆ?", "tr": "Bus nildana ellide?", "syllables": "Bus nil-da-na el-li-de?", "tone": "Conversational", "context": "Essential transit inquiry for KSRTC or BMTC bus stations."},
    "where is the railway station": {"meaning": "Where is the railway station?", "kn": "ರೈಲ್ವೆ ನಿಲ್ದಾಣ ಎಲ್ಲಿದೆ?", "tr": "Railway nildana ellide?", "syllables": "Rail-way nil-da-na el-li-de?", "tone": "Conversational", "context": "Asking directions to the nearest train junction."},
    "how much is the auto fare": {"meaning": "How much will the auto fare be?", "kn": "ಆಟೋ ಬಾಡಿಗೆ ಎಷ್ಟು ಆಗುತ್ತೆ?", "tr": "Auto baadige eshtu aagutte?", "syllables": "Au-to baa-di-ge esh-tu aa-gut-te?", "tone": "Everyday Market", "context": "Crucial query when taking an auto-rickshaw across Karnataka."},
    "please turn on the meter": {"meaning": "Please turn on the meter", "kn": "ದಯವಿಟ್ಟು ಮೀಟರ್ ಹಾಕಿ", "tr": "Dayavittu meter haaki", "syllables": "Da-ya-vit-tu mee-ter haa-ki", "tone": "Polite Assertion", "context": "Asking auto driver in Bengaluru, Mysuru, or Hubballi to run on meter."},
    "will you come to": {"meaning": "Will you come to this place?", "kn": "ಇಲ್ಲಿಗೆ ಬರುತ್ತೀರಾ?", "tr": "Illige barutteera?", "syllables": "Il-li-ge ba-rut-tee-ra?", "tone": "Polite", "context": "Asking auto or taxi driver if they will take you to your destination."},
    "stop here": {"meaning": "Please stop here / Drop me here", "kn": "ಇಲ್ಲೇ ನಿಲ್ಲಿಸಿ", "tr": "Ille nillisi", "syllables": "Il-le nil-li-si", "tone": "Conversational", "context": "Telling a driver to drop you off right here."},
    "go straight": {"meaning": "Go straight ahead", "kn": "ನೇರವಾಗಿ ಹೋಗಿ", "tr": "Nera-vaagi hogi", "syllables": "Ne-ra-vaa-gi ho-gi", "tone": "Direction", "context": "Directing a driver or navigator."},
    "turn left": {"meaning": "Turn left", "kn": "ಎಡಕ್ಕೆ ತಿರುಗಿ", "tr": "Edakke tirugi", "syllables": "E-dak-ke ti-ru-gi", "tone": "Direction", "context": "Navigation instruction."},
    "turn right": {"meaning": "Turn right", "kn": "ಬಲಕ್ಕೆ ತಿರುಗಿ", "tr": "Balakke tirugi", "syllables": "Ba-lak-ke ti-ru-gi", "tone": "Direction", "context": "Navigation instruction."},

    # Food & Darshini Dining
    "where can i get water": {"meaning": "Where can I get drinking water?", "kn": "ಕುಡಿಯುವ ನೀರು ಎಲ್ಲಿ ಸಿಗುತ್ತದೆ?", "tr": "Kudiyuva neeru elli siguttade?", "syllables": "Ku-di-yu-va nee-ru el-li si-gut-ta-de?", "tone": "Polite", "context": "Asking for potable drinking water."},
    "please give water": {"meaning": "Please give me drinking water", "kn": "ದಯವಿಟ್ಟು ನೀರು ಕೊಡಿ", "tr": "Dayavittu neeru kodi", "syllables": "Da-ya-vit-tu nee-ru ko-di", "tone": "Polite Request", "context": "Asking for a glass or bottle of water."},
    "please give one plate idli vada": {"meaning": "Please give one plate idli vada", "kn": "ಒಂದು ಪ್ಲೇಟ್ ಇಡ್ಲಿ ವಡೆ ಕೊಡಿ", "tr": "Ondu plate idli vade kodi", "syllables": "On-du plate id-li va-de ko-di", "tone": "Darshini Classic", "context": "The quintessential Karnataka breakfast order at darshinis."},
    "one cup filter coffee please": {"meaning": "One cup of filter coffee, please", "kn": "ಒಂದು ಕಪ್ ಫಿಲ್ಟರ್ ಕಾಫಿ ಕೊಡಿ", "tr": "Ondu cup filter coffee kodi", "syllables": "On-du cup fil-ter cof-fee ko-di", "tone": "Darshini Classic", "context": "Ordering traditional Karnataka filter kaapi."},
    "two cups tea please": {"meaning": "Two cups of tea, please", "kn": "ಎರಡು ಕಪ್ ಟೀ ಕೊಡಿ", "tr": "Eradu cup tea kodi", "syllables": "E-ra-du cup tea ko-di", "tone": "Conversational", "context": "Ordering chai for two."},
    "is pure vegetarian food available": {"meaning": "Is pure vegetarian food available here?", "kn": "ಇಲ್ಲಿ ಶುದ್ಧ ಸಸ್ಯಾಹಾರಿ ಊಟ ಸಿಗುತ್ತದೆಯೇ?", "tr": "Illi shuddha sasyaahaari oota siguttadeye?", "syllables": "Il-li shud-dha sas-yaa-haa-ri oo-ta si-gut-ta-de-ye?", "tone": "Polite Inquiry", "context": "Checking for vegetarian dietary compliance."},
    "the food is delicious": {"meaning": "The food is very delicious!", "kn": "ಊಟ ತುಂಬಾ ರುಚಿಯಾಗಿದೆ!", "tr": "Oota tumba ruchiyaagide!", "syllables": "Oo-ta tum-ba ru-chi-yaa-gi-de!", "tone": "Complimentary", "context": "Appreciating local culinary hospitality."},
    "please give the bill": {"meaning": "Please give me the bill", "kn": "ದಯವಿಟ್ಟು ಬಿಲ್ ಕೊಡಿ", "tr": "Dayavittu bill kodi", "syllables": "Da-ya-vit-tu bill ko-di", "tone": "Polite", "context": "Requesting the restaurant bill."},

    # Market, Shopping & Payments
    "how much does this cost": {"meaning": "How much does this cost?", "kn": "ಇದರ ಬೆಲೆ ಎಷ್ಟು?", "tr": "Idara bele eshtu?", "syllables": "I-da-ra be-le esh-tu?", "tone": "Standard Market", "context": "Asking the price of any item or souvenir."},
    "please reduce the price a little": {"meaning": "Please reduce the price a little", "kn": "ಸ್ವಲ್ಪ ಬೆಲೆ ಕಡಿಮೆ ಮಾಡಿ", "tr": "Svalpa bele kadime maadi", "syllables": "Sval-pa be-le ka-di-me maa-di", "tone": "Gentle Bargaining", "context": "Polite bargaining in traditional Karnataka markets."},
    "do you accept upi or google pay": {"meaning": "Do you accept UPI or Google Pay?", "kn": "ಯುಪಿಐ ಅಥವಾ ಗೂಗಲ್ ಪೇ ಇದೆಯಾ?", "tr": "UPI athava Google Pay ideya?", "syllables": "U-P-I a-tha-va Goo-gle Pay i-de-ya?", "tone": "Everyday Commerce", "context": "Checking for digital QR code payments."},
    "where is the nearest atm": {"meaning": "Where is the nearest ATM?", "kn": "ಹತ್ತಿರದ ಎಟಿಎಂ ಎಲ್ಲಿದೆ?", "tr": "Hattirada ATM ellide?", "syllables": "Hat-ti-ra-da A-T-M el-li-de?", "tone": "Inquiry", "context": "Finding an ATM to withdraw cash."},

    # Sightseeing, Heritage & Temples
    "what time does the temple open": {"meaning": "What time does the temple open?", "kn": "ದೇವಾಲಯ ಯಾವ ಸಮಯಕ್ಕೆ ತೆರೆಯುತ್ತದೆ?", "tr": "Devaalaya yaava samayakke tereyuttade?", "syllables": "De-vaa-la-ya yaa-va sa-ma-yak-ke te-re-yut-ta-de?", "tone": "Polite", "context": "Checking temple darshan hours."},
    "where is the ticket counter": {"meaning": "Where is the ticket counter?", "kn": "ಟಿಕೆಟ್ ಕೌಂಟರ್ ಎಲ್ಲಿದೆ?", "tr": "Ticket counter ellide?", "syllables": "Tic-ket coun-ter el-li-de?", "tone": "Sightseeing", "context": "Locating entry ticket counter at monuments and parks."},
    "is photography allowed": {"meaning": "Is photography permitted here?", "kn": "ಇಲ್ಲಿ ಫೋಟೋ ತೆಗೆಯಲು ಅನುಮತಿ ಇದೆಯೇ?", "tr": "Illi photo tegeyalu anumati ideye?", "syllables": "Il-li pho-to te-ge-ya-lu a-nu-ma-ti i-de-ye?", "tone": "Polite Check", "context": "Confirming camera permits at archaeological sites."},

    # Emergency & Assistance
    "can you please help me": {"meaning": "Could you please help me?", "kn": "ದಯವಿಟ್ಟು ನನಗೆ ಸಹಾಯ ಮಾಡುವಿರಾ?", "tr": "Dayavittu nanage sahaaya maaduveera?", "syllables": "Da-ya-vit-tu na-na-ge sa-haa-ya maa-du-vee-ra?", "tone": "Polite Request", "context": "Seeking urgent guidance from a bystander."},
    "where is the nearest hospital": {"meaning": "Where is the nearest hospital?", "kn": "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಎಲ್ಲಿದೆ?", "tr": "Hattirada aaspatre ellide?", "syllables": "Hat-ti-ra-da aas-pat-re el-li-de?", "tone": "Urgent Medical", "context": "Medical emergency inquiry."},
    "i do not know kannada": {"meaning": "I do not know Kannada very well", "kn": "ನನಗೆ ಕನ್ನಡ ಚೆನ್ನಾಗಿ ಬರಲ್ಲ", "tr": "Nanage Kannada chennaagi baralla", "syllables": "Na-na-ge Kan-na-da chen-naa-gi ba-ral-la", "tone": "Friendly Honest", "context": "Letting locals know you are learning or visiting."},
    "i am learning kannada": {"meaning": "I am learning Kannada", "kn": "ನಾನು ಕನ್ನಡ ಕಲಿಯುತ್ತಿದ್ದೇನೆ", "tr": "Naanu Kannada kaliyuttiddene", "syllables": "Naa-nu Kan-na-da ka-li-yut-tid-de-ne", "tone": "Warm & Endearing", "context": "Earns immense warmth and smiles from locals across Karnataka!"},
}

# Cross-language mappings for common queries (native scripts & romanized variants)
CROSS_LANG_MAPPINGS = {
    # Hindi (Devanagari)
    "नमस्ते": "hello", "धन्यवाद": "thank you", "बहुत धन्यवाद": "thank you very much",
    "आप कैसे हैं": "how are you", "बस स्टैंड कहाँ है": "where is the bus stand",
    "रेलवे स्टेशन कहाँ है": "where is the railway station",
    "ऑटो का किराया कितना है": "how much is the auto fare",
    "कृपया मीटर चालू करें": "please turn on the meter",
    "यहाँ रोकिए": "stop here", "सीधे जाइए": "go straight",
    "बाएँ मुड़िए": "turn left", "दाएँ मुड़िए": "turn right",
    "पीने का पानी कहाँ मिलेगा": "where can i get water",
    "कृपया पानी दीजिए": "please give water",
    "इसकी कीमत क्या है": "how much does this cost",
    "थोड़ा कम कीजिए": "please reduce the price a little",
    "गूगल पे है क्या": "do you accept upi or google pay",
    "पास में एटीएम कहाँ है": "where is the nearest atm",
    "मंदिर कब खुलता है": "what time does the temple open",
    "टिकट काउंटर कहाँ है": "where is the ticket counter",
    "क्या आप मेरी मदद कर सकते हैं": "can you please help me",
    "मुझे कन्नड़ नहीं आती": "i do not know kannada",
    # Telugu (Script)
    "నమస్కారం": "hello", "ధన్యవాదాలు": "thank you", "చాలా ధన్యవాదాలు": "thank you very much",
    "మీరు ఎలా ఉన్నారు": "how are you", "బస్ స్టాండ్ ఎక్కడ ఉంది": "where is the bus stand",
    "రైల్వే స్టేషన్ ఎక్కడ ఉంది": "where is the railway station",
    "ఆటో ఛార్జీ ఎంత": "how much is the auto fare",
    "దయచేసి మీటర్ వేయండి": "please turn on the meter",
    "ఇక్కడ ఆపండి": "stop here",
    "మంచినీళ్లు ఎక్కడ దొరుకుతాయి": "where can i get water",
    "దీని ధర ఎంత": "how much does this cost",
    "కొంచెం తగ్గించండి": "please reduce the price a little",
    "నాకు సహాయం చేయగలరా": "can you please help me",
    # Tamil (Script)
    "வணக்கம்": "hello", "நன்றி": "thank you", "மிக்க நன்றி": "thank you very much",
    "எப்படி இருக்கிறீர்கள்": "how are you", "பேருந்து நிலையம் எங்கே": "where is the bus stand",
    "ரயில் நிலையம் எங்கே": "where is the railway station",
    "ஆட்டோ கட்டணம் எவ்வளவு": "how much is the auto fare",
    "தயவுசெய்து மீட்டர் போடுங்கள்": "please turn on the meter",
    "இங்கே நிறுத்துங்கள்": "stop here",
    "குடிநீர் எங்கே கிடைக்கும்": "where can i get water",
    "இதன் விலை என்ன": "how much does this cost",
    "கொஞ்சம் குறைத்துக் கொடுங்கள்": "please reduce the price a little",
    "உதவ முடியுமா": "can you please help me",
    # Malayalam (Script)
    "നമസ്കാരം": "hello", "നന്ദി": "thank you", "വളരെ നന്ദി": "thank you very much",
    "സുഖമാണോ": "how are you", "ബസ് സ്റ്റാൻഡ് എവിടെയാണ്": "where is the bus stand",
    "റെയിൽവേ സ്റ്റേഷൻ എവിടെയാണ്": "where is the railway station",
    "ഓട്ടോ കൂലി എത്രയാണ്": "how much is the auto fare",
    "ദയവായി മീറ്റർ ഇടൂ": "please turn on the meter",
    "ഇവിടെ നിർത്തൂ": "stop here",
    "വെള്ളം എവിടെ കിട്ടും": "where can i get water",
    "ഇതിന് എത്ര രൂപയാണ്": "how much does this cost",
    "കുറച്ച് കുറയ്ക്കുമോ": "please reduce the price a little",
    "സഹായിക്കാമോ": "can you please help me",

    # Hinglish (Romanized Hindi + English)
    "namaste": "hello", "namaskar": "hello", "dhanyawad": "thank you", "dhanyavaad": "thank you",
    "shukriya": "thank you", "bahut dhanyawad": "thank you very much",
    "aap kaise ho": "how are you", "kaise ho": "how are you", "kaise hain": "how are you",
    "bus stand kahan hai": "where is the bus stand", "bus stand kidhar hai": "where is the bus stand",
    "railway station kahan hai": "where is the railway station", "railway station kidhar hai": "where is the railway station",
    "auto ka kiraya kitna hai": "how much is the auto fare", "auto ka charge kitna hai": "how much is the auto fare",
    "meter chalu karo": "please turn on the meter", "meter se chalo": "please turn on the meter",
    "kripya meter chalu karein": "please turn on the meter",
    "yahan rokiye": "stop here", "yahan roko": "stop here",
    "seedhe jaiye": "go straight", "seedhe jao": "go straight",
    "left mudo": "turn left", "right mudo": "turn right",
    "paani kahan milega": "where can i get water", "pani kahan milega": "where can i get water",
    "pani dijiye": "please give water", "paani dijiye": "please give water",
    "isiki keemat kya hai": "how much does this cost", "kitna hua": "how much does this cost", "kitna hai": "how much does this cost",
    "thoda kam kijiye": "please reduce the price a little", "thoda kam karo": "please reduce the price a little",
    "google pay hai kya": "do you accept upi or google pay", "upi chalega": "do you accept upi or google pay",
    "pass me atm kahan hai": "where is the nearest atm", "atm kahan hai": "where is the nearest atm",
    "mandir kab khulta hai": "what time does the temple open",
    "ticket counter kahan hai": "where is the ticket counter",
    "kripya meri madad kijiye": "can you please help me", "madad kar sakte hain": "can you please help me",
    "mujhe kannada nahi aati": "i do not know kannada", "kannada nahi aati": "i do not know kannada",

    # Tanglish (Romanized Tamil + English)
    "vanakkam": "hello", "nandri": "thank you", "romba nandri": "thank you very much", "mikka nandri": "thank you very much",
    "eppadi irukkeenga": "how are you", "eppadi irukkinga": "how are you",
    "bus stand enga irukku": "where is the bus stand", "bus stand enga": "where is the bus stand",
    "railway station enga irukku": "where is the railway station",
    "auto fare evlo": "how much is the auto fare", "auto charge evlo": "how much is the auto fare",
    "meter podunga": "please turn on the meter", "meter poduveengala": "please turn on the meter",
    "inge niruthunga": "stop here", "ingaye nillunga": "stop here",
    "neraa ponga": "go straight", "idathu pakkam": "turn left", "valathu pakkam": "turn right",
    "thanni enga kedaikkum": "where can i get water", "thanni kedaikkuma": "where can i get water",
    "thanni kudunga": "please give water", "oru filter coffee kudunga": "one cup filter coffee please",
    "idhu evlo": "how much does this cost", "vila enna": "how much does this cost", "evlo aagum": "how much does this cost",
    "konjam kurainga": "please reduce the price a little", "konjam korainga": "please reduce the price a little",
    "gpay irukka": "do you accept upi or google pay", "upi irukka": "do you accept upi or google pay",
    "pakkathula atm enga": "where is the nearest atm", "atm enga irukku": "where is the nearest atm",
    "kovil eppo thirakkum": "what time does the temple open",
    "ticket counter enga": "where is the ticket counter",
    "udhavi seiyya mudiyuma": "can you please help me", "help panna mudiyuma": "can you please help me",
    "enakku kannada theriyadhu": "i do not know kannada",

    # Manglish (Romanized Malayalam + English)
    "namaskaram": "hello", "nanni": "thank you", "valare nanni": "thank you very much",
    "sukhamaano": "how are you", "sukhamano": "how are you",
    "bus stand evideyaanu": "where is the bus stand", "bus stand evide": "where is the bus stand",
    "railway station evideyaanu": "where is the railway station",
    "auto kooli ethraya": "how much is the auto fare", "auto charge ethra": "how much is the auto fare",
    "meter idamo": "please turn on the meter", "meter idumo": "please turn on the meter",
    "ivide nirthu": "stop here", "ivide nirthamo": "stop here",
    "nere poku": "go straight", "idathottu": "turn left", "valathottu": "turn right",
    "vellam evide kittum": "where can i get water", "vellam tharumo": "please give water",
    "oru cup chaya tharumo": "two cups tea please",
    "ithinu ethra roopayaanu": "how much does this cost", "ethraya": "how much does this cost",
    "kurachu kurakkumo": "please reduce the price a little",
    "gpay undoo": "do you accept upi or google pay", "upi undoo": "do you accept upi or google pay",
    "adutha atm evide": "where is the nearest atm",
    "ambalam eppozha thurakkuka": "what time does the temple open",
    "ticket counter evideyaanu": "where is the ticket counter",
    "sahayikkamo": "can you please help me", "help cheyyamo": "can you please help me",
    "enikku kannada ariyilla": "i do not know kannada",

    # Tenglish (Romanized Telugu + English)
    "dhanyavadalu": "thank you", "chala dhanyavadalu": "thank you very much",
    "ela unnaru": "how are you", "ela unnaaru": "how are you",
    "bus stand ekkada undi": "where is the bus stand", "bus stand ekkada": "where is the bus stand",
    "railway station ekkada undi": "where is the railway station",
    "auto charge entha": "how much is the auto fare", "auto ki entha": "how much is the auto fare",
    "meter veyyandi": "please turn on the meter", "meter vesthara": "please turn on the meter",
    "ikkada aapandi": "stop here", "ikkade aapandi": "stop here",
    "seedha vellandi": "go straight", "edamavaipu": "turn left", "kudivaipu": "turn right",
    "manchineellu ekkada dorukuthayi": "where can i get water", "neellu ekkada": "where can i get water",
    "neellu ivvandi": "please give water", "manchineellu ivvandi": "please give water",
    "deeni dhara entha": "how much does this cost", "entha avuthundi": "how much does this cost",
    "konchem thagginchandi": "please reduce the price a little", "konchem thagginchara": "please reduce the price a little",
    "gpay unda": "do you accept upi or google pay", "upi unda": "do you accept upi or google pay",
    "daggarloni atm ekkada": "where is the nearest atm",
    "gudi eppudu therustharu": "what time does the temple open",
    "ticket counter ekkada": "where is the ticket counter",
    "sahayam cheyagalara": "can you please help me", "help cheyagalara": "can you please help me",
    "naaku kannada raadu": "i do not know kannada",
}

LANG_NAMES = {
    "en": "English", "hi": "Hindi", "te": "Telugu",
    "ta": "Tamil", "ml": "Malayalam", "kn": "Kannada",
}


def clean_query(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r'[?!.,;:"\'()\-]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def generate_kannada_transliteration(kannada_text: str) -> str:
    """Produces readable Latin transliteration for Kannada script."""
    char_map = {
        'ಅ': 'a', 'ಆ': 'aa', 'ಇ': 'i', 'ಈ': 'ee', 'ಉ': 'u', 'ಊ': 'oo',
        'ಋ': 'ru', 'ಎ': 'e', 'ಏ': 'ae', 'ಐ': 'ai', 'ಒ': 'o', 'ಓ': 'oa', 'ಔ': 'au',
        'ಕ': 'ka', 'ಖ': 'kha', 'ಗ': 'ga', 'ಘ': 'gha', 'ಙ': 'nga',
        'ಚ': 'cha', 'ಛ': 'chha', 'ಜ': 'ja', 'ಝ': 'jha', 'ಞ': 'nya',
        'ಟ': 'ta', 'ಠ': 'tha', 'ಡ': 'da', 'ಢ': 'dha', 'ಣ': 'na',
        'ತ': 'ta', 'ಥ': 'tha', 'ದ': 'da', 'ಧ': 'dha', 'ನ': 'na',
        'ಪ': 'pa', 'ಫ': 'pha', 'ಬ': 'ba', 'ಭ': 'bha', 'ಮ': 'ma',
        'ಯ': 'ya', 'ರ': 'ra', 'ಲ': 'la', 'ವ': 'va', 'ಶ': 'sha',
        'ಷ': 'sha', 'ಸ': 'sa', 'ಹ': 'ha', 'ಳ': 'la',
        'ಾ': 'aa', 'ಿ': 'i', 'ೀ': 'ee', 'ು': 'u', 'ೂ': 'oo', 'ೃ': 'ru',
        'ೆ': 'e', 'ೇ': 'ae', 'ೈ': 'ai', 'ೊ': 'o', 'ೋ': 'oa', 'ೌ': 'au',
        '್': '', 'ಂ': 'm', 'ಃ': 'h',
    }
    res = []
    for ch in kannada_text:
        if ch in char_map:
            res.append(char_map[ch])
        else:
            res.append(ch)
    return "".join(res)


def query_gemini_translation(text: str, source_lang: str = "en", api_key: str = "") -> Optional[Dict[str, Any]]:
    """
    Uses Google Gemini API to translate text to authentic spoken Kannada.
    Specialized for romanized Indian dialects: Hinglish, Tanglish, Manglish, Tenglish.
    Returns a dict with keys: kannada, transliteration, syllables, tone, context, or None on failure.
    """
    if not api_key or api_key == "your_gemini_api_key_here":
        return None

    try:
        from google import genai
        from google.genai import types

        lang_name = LANG_NAMES.get(source_lang, "Indian language / English")

        prompt = f"""You are an expert Karnataka Kannada linguist and local cultural guide.
Your mission is to understand traveler phrases typed in informal Indian romanized blends and translate them into authentic, natural, polite spoken Kannada.

The input can be in:
1. Hinglish (Hindi in Roman script + English, e.g. 'mujhe bus stand jana hai', 'pani kahan milega', 'bhaiya auto meter chalao')
2. Tanglish (Tamil in Roman script + English, e.g. 'bus stand enga irukku', 'thanni enga kedaikkum', 'auto meter poduveengala', 'oru filter coffee kudunga')
3. Manglish (Malayalam in Roman script + English, e.g. 'bus stand evideyaanu', 'vellam evide kittum', 'auto kooli ethraya', 'oru chaya tharumo')
4. Tenglish (Telugu in Roman script + English, e.g. 'bus stand ekkada undi', 'manchineellu ekkada dorukuthayi', 'auto charge entha', 'market ki ela vellali')
5. Standard English or native Indian scripts (Devanagari, Tamil, Telugu, Malayalam).

Selected language hint: {lang_name} (Note: user may be typing Romanized/mixed script)
Input text: "{text}"

Linguistic Guidelines for translation:
- First, extract the core intention and traveler meaning (greeting, asking directions, ordering food, auto negotiation, medical help, payments).
- Translate into idiomatic, everyday spoken Kannada as used on the streets of Bengaluru, Mysuru, Hubballi, and Coastal Karnataka.
- Respectful suffix "-ri" or "-ra" for polite conversation (e.g. "ಹೋಗಿ", "ಕೊಡಿ", "ಹಾಕುತ್ತೀರಾ").

Output strictly a JSON object with no markdown fences, no backticks:
{{
  "kannada": "<MUST BE IN KANNADA SCRIPT (ಕನ್ನಡ ಲಿಪಿ) ONLY. Never in English alphabet.>",
  "meaning": "<Clear, concise English meaning/interpretation of what this expression means>",
  "transliteration": "<English phonetic pronunciation of the Kannada, e.g. 'Namaskara, nanage neeru beku'>",
  "syllables": "<Syllables breakdown for pronunciation, e.g. 'Na-mas-kaa-ra, na-na-ge nee-ru be-ku'>",
  "tone": "<Courteous, Conversational, Market, Transit, Direction, or Respectful>",
  "context": "<One short practical sentence on how and when a traveler should use this in Karnataka>"
}}
"""

        client = genai.Client(api_key=api_key)
        candidate_models = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
        last_error = None

        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=512,
                    )
                )

                raw = response.text.strip()
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)

                result = json.loads(raw)
                required = ["kannada", "transliteration", "syllables", "tone", "context"]
                if all(k in result for k in required) and result.get("kannada"):
                    kn_text = result["kannada"].strip()
                    # Ensure the output contains authentic Kannada Unicode script characters
                    if any('\u0C80' <= c <= '\u0CFF' for c in kn_text):
                        if not result.get("meaning"):
                            result["meaning"] = text
                        return result
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini model {model_name} error: {e}")
                continue

        if last_error:
            logger.warning(f"All Gemini models exhausted. Last error: {last_error}")

    except Exception as e:
        logger.warning("Gemini translation failed: %s", e)

    return None


def query_online_translation(text: str, source_lang: str = "en") -> Optional[str]:
    """MyMemory API fallback with timeout."""
    try:
        source_code = source_lang if source_lang in ["en", "hi", "te", "ta", "ml"] else "en"
        encoded = urllib.parse.quote(text.strip())
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair={source_code}|kn"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "NammaPayana-TouristCompanion/3.0 (Karnataka Innovation Hackathon)"}
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and data.get("responseData"):
                translated = data["responseData"].get("translatedText")
                if translated and not translated.startswith("MYMEMORY WARNING"):
                    return translated.strip()
    except Exception as e:
        logger.warning("MyMemory translation failed: %s", e)
    return None


class TranslatorService:
    def __init__(self):
        self._gemini_api_key = ""
        self._load_config()

    def _load_config(self):
        """Reads the Gemini API key from environment/config at startup."""
        try:
            import config
            self._gemini_api_key = getattr(config, "GEMINI_API_KEY", "")
        except Exception:
            import os
            self._gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    @staticmethod
    def translate(text: str, source_lang: str = "en") -> Dict[str, Any]:
        """
        Translation priority:
        1. Verified lexicon (fast path for canonical phrases)
        2. Cross-language mappings (exact matches for Devanagari/Tamil/Telugu/Malayalam and Hinglish/Tanglish/Manglish/Tenglish)
        3. Google Gemini AI (primary intelligence engine for arbitrary sentences, romanized dialects, and queries)
        4. MyMemory API (network fallback)
        5. Smart lexicon fallback (word-level match when offline)
        6. Friendly fallback expression
        """
        raw_text = (text or "").strip()
        if not raw_text:
            return {"ok": False, "error": "Input text cannot be empty."}

        cleaned = clean_query(raw_text)

        # 1. Direct verified lexicon match (canonical English keys)
        if cleaned in VERIFIED_LEXICON:
            entry = VERIFIED_LEXICON[cleaned]
            return {
                "ok": True,
                "data": {
                    "source_text": raw_text, "source_lang": source_lang,
                    "kannada": entry["kn"], "transliteration": entry["tr"],
                    "meaning": entry.get("meaning", cleaned.capitalize()),
                    "syllables": entry["syllables"], "tone": entry["tone"],
                    "context": entry["context"], "verified": True,
                    "source": "Namma Payana Verified Lexicon"
                }
            }

        # 2. Exact match in Cross-language mappings (Native scripts + Romanized Hinglish/Tanglish/Manglish/Tenglish)
        raw_stripped = raw_text.strip()
        matched_key = None
        if cleaned in CROSS_LANG_MAPPINGS:
            matched_key = CROSS_LANG_MAPPINGS[cleaned]
        elif raw_stripped in CROSS_LANG_MAPPINGS:
            matched_key = CROSS_LANG_MAPPINGS[raw_stripped]

        if matched_key and matched_key in VERIFIED_LEXICON:
            entry = VERIFIED_LEXICON[matched_key]
            return {
                "ok": True,
                "data": {
                    "source_text": raw_text, "source_lang": source_lang,
                    "kannada": entry["kn"], "transliteration": entry["tr"],
                    "meaning": entry.get("meaning", matched_key.capitalize()),
                    "syllables": entry["syllables"], "tone": entry["tone"],
                    "context": entry["context"], "verified": True,
                    "source": "Namma Payana Multilingual Lexicon"
                }
            }

        # 3. Google Gemini AI (primary dynamic engine for sentences & romanized dialects)
        api_key = ""
        try:
            import config
            api_key = getattr(config, "GEMINI_API_KEY", "")
        except Exception:
            import os
            api_key = os.environ.get("GEMINI_API_KEY", "")

        if api_key and api_key != "your_gemini_api_key_here":
            gemini_result = query_gemini_translation(raw_text, source_lang=source_lang, api_key=api_key)
            if gemini_result:
                return {
                    "ok": True,
                    "data": {
                        "source_text": raw_text, "source_lang": source_lang,
                        "kannada": gemini_result["kannada"],
                        "meaning": gemini_result.get("meaning") or raw_text,
                        "transliteration": gemini_result["transliteration"],
                        "syllables": gemini_result["syllables"],
                        "tone": gemini_result["tone"],
                        "context": gemini_result["context"],
                        "verified": False,
                        "source": "Gemini AI Spoken Kannada Engine"
                    }
                }

        # 4. MyMemory API fallback
        online_result = query_online_translation(raw_text, source_lang=source_lang)
        if online_result:
            tr = generate_kannada_transliteration(online_result)
            return {
                "ok": True,
                "data": {
                    "source_text": raw_text, "source_lang": source_lang,
                    "kannada": online_result,
                    "meaning": raw_text,
                    "transliteration": tr if tr else online_result,
                    "syllables": tr if tr else online_result,
                    "tone": "Conversational",
                    "context": "Spoken translation for Karnataka travel.",
                    "verified": False,
                    "source": "Dynamic Translation Engine"
                }
            }

        # 5. Smart token-based fallback matching in verified lexicon (only if offline and strong match)
        input_words = set(cleaned.split())
        if len(input_words) > 1:
            best_match = None
            best_score = 0
            for key, entry in VERIFIED_LEXICON.items():
                key_words = set(key.split())
                overlap = len(input_words & key_words)
                score = overlap / max(len(input_words), len(key_words))
                if score > best_score and score >= 0.5:
                    best_score = score
                    best_match = entry

            if best_match:
                return {
                    "ok": True,
                    "data": {
                        "source_text": raw_text, "source_lang": source_lang,
                        "kannada": best_match["kn"], "transliteration": best_match["tr"],
                        "meaning": best_match.get("meaning", "Closest idiomatic expression"),
                        "syllables": best_match["syllables"], "tone": best_match["tone"],
                        "context": best_match["context"], "verified": True,
                        "source": "Namma Payana Closest Idiomatic Match"
                    }
                }

        # 6. Courteous fallback expression
        fallback = VERIFIED_LEXICON["can you please help me"]
        return {
            "ok": True,
            "data": {
                "source_text": raw_text, "source_lang": source_lang,
                "kannada": fallback["kn"], "transliteration": fallback["tr"],
                "meaning": fallback.get("meaning", "Could you please help me?"),
                "syllables": fallback["syllables"], "tone": "Courteous",
                "context": "Recommended polite traveler expression.",
                "verified": True, "source": "Recommended Fallback Expression"
            }
        }


translator_service = TranslatorService()
