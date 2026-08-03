from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EditorialTopic:
    title: str
    category: str
    angle: str
    facts: tuple[str, ...]
    public_questions: tuple[str, ...]
    reference_name: str
    reference_url: str


CORE_REFERENCES = {
    "exam": (
        "Public Examinations (Prevention of Unfair Means) Act, 2024 and Ministry of Education exam reform updates",
        "https://prsindia.org/billtrack/the-public-examinations-prevention-of-unfair-means-bill-2024",
    ),
    "nta": (
        "Ministry of Education High-Level Committee on examination reforms",
        "https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=2027892&lang=2&reg=48",
    ),
    "e20": (
        "Ministry of Petroleum and Natural Gas E20 petrol clarification",
        "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2288269&lang=1&reg=1",
    ),
    "civic": (
        "Official public communication and local administration updates",
        "",
    ),
}


BASE_TOPICS = [
    (
        "जंतर मंतर छात्र आंदोलन के बाद भारत में जनभावना किस दिशा में जा सकती है",
        "Politics",
        "छात्र आंदोलनों के असर को चुनावी शोर से अलग रखकर जनविश्वास और जवाबदेही के संदर्भ में समझना।",
        "exam",
    ),
    (
        "पेपर लीक विवाद के बाद छात्र किस तरह की शिक्षा व्यवस्था चाहते हैं",
        "Education",
        "परीक्षा सुरक्षा, समय पर जांच और पारदर्शी grievance redressal पर केंद्रित विश्लेषण।",
        "nta",
    ),
    (
        "E20 पेट्रोल पर लोगों की चिंता: माइलेज, भरोसा और सरकारी सफाई को कैसे समझें",
        "Auto",
        "E20 पर सरकार के दावों और वाहन मालिकों की वास्तविक चिंताओं को संतुलित तरीके से समझाना।",
        "e20",
    ),
    (
        "पेपर लीक रोकने के लिए शिक्षा विभाग को कौन से 10 कदम तुरंत उठाने चाहिए",
        "Education",
        "डेटा सुरक्षा, प्रिंटिंग, लॉजिस्टिक्स, डिजिटल ट्रैकिंग और जवाबदेही मॉडल पर व्यावहारिक सुझाव।",
        "nta",
    ),
    (
        "युवा मतदाता अब किस तरह की राजनीति को महत्व दे सकते हैं",
        "Politics",
        "रोजगार, परीक्षा निष्पक्षता, महंगाई और संस्थागत भरोसे के आधार पर मतदाता प्राथमिकताओं का विश्लेषण।",
        "exam",
    ),
]


QUESTION_BANK = {
    "exam": (
        "क्या परीक्षा प्रक्रिया पर छात्रों का भरोसा लौट सकता है?",
        "किस स्तर पर जवाबदेही तय होनी चाहिए?",
        "क्या कानून के साथ प्रशासनिक सुधार भी जरूरी हैं?",
    ),
    "nta": (
        "NTA और परीक्षा एजेंसियों की भूमिका कैसे साफ होनी चाहिए?",
        "डेटा सुरक्षा और पेपर सुरक्षा में कौन सी कमियां जोखिम बनती हैं?",
        "छात्रों को शिकायत पर समयबद्ध जवाब कैसे मिल सकता है?",
    ),
    "e20": (
        "क्या पुराने वाहन मालिकों को अलग मार्गदर्शन मिलना चाहिए?",
        "माइलेज और रखरखाव पर भरोसेमंद जानकारी कैसे मिले?",
        "सरकार, कंपनियों और उपभोक्ताओं के बीच संवाद कैसे बेहतर हो?",
    ),
    "civic": (
        "स्थानीय प्रशासन को जनता को कितनी जल्दी जानकारी देनी चाहिए?",
        "अफवाहों से बचने के लिए नागरिक क्या करें?",
        "समस्या का स्थायी समाधान कैसे निकले?",
    ),
}


FACT_BANK = {
    "exam": (
        "भारत में सार्वजनिक परीक्षाओं को सुरक्षित बनाने के लिए 2024 में Public Examinations law लाया गया।",
        "कानून पेपर लीक, answer key leak, fake exam और संगठित cheating जैसे unfair means को अपराध मानता है।",
        "कानून जरूरी है, लेकिन सुरक्षित परीक्षा के लिए SOP, technology, logistics और जवाबदेही भी उतनी ही जरूरी है।",
    ),
    "nta": (
        "Ministry of Education ने 2024 में NTA exam process, data security और agency structure की समीक्षा के लिए high-level committee बनाई।",
        "Committee के terms में end-to-end exam process, SOP review, data security protocols और grievance mechanism शामिल थे।",
        "Exam reform सिर्फ punishment नहीं, prevention, transparency और student communication का भी सवाल है।",
    ),
    "e20": (
        "E20 petrol में 20 percent ethanol और 80 percent petrol होता है।",
        "Petroleum Ministry ने कहा है कि rollout scientific validation और automobile industry consultation के साथ किया गया।",
        "लोगों की चिंता मुख्य रूप से mileage, old vehicle compatibility, maintenance cost और clear communication से जुड़ी है।",
    ),
    "civic": (
        "Public-interest issues में official confirmation और timely communication भरोसा बनाने के लिए जरूरी होते हैं।",
        "स्थानीय स्तर पर लिखित आदेश, helpline और grievance process misinformation कम कर सकते हैं।",
        "नागरिकों को viral claims की जगह official sources और documented complaints पर भरोसा करना चाहिए।",
    ),
}


def generate_editorial_topics(limit=100):
    topics = []
    focus_variants = [
        "छात्रों",
        "अभिभावकों",
        "युवा मतदाताओं",
        "ग्रामीण परिवारों",
        "शहरी मध्यम वर्ग",
        "कोचिंग छात्रों",
        "सरकारी नौकरी अभ्यर्थियों",
        "छोटे शहरों",
        "स्थानीय प्रशासन",
        "नीति निर्माताओं",
        "पुराने वाहन मालिकों",
        "नए वाहन खरीदारों",
        "किसानों",
        "ऑटोमोबाइल बाजार",
        "ईंधन उपभोक्ताओं",
        "राजनीतिक दलों",
        "विपक्ष",
        "सत्तारूढ़ दल",
        "सोशल मीडिया",
        "न्याय व्यवस्था",
    ]
    for index in range(limit):
        base_title, category, angle, key = BASE_TOPICS[index % len(BASE_TOPICS)]
        focus = focus_variants[index % len(focus_variants)]
        reference_name, reference_url = CORE_REFERENCES[key]
        title = f"{base_title}: {focus} के लिए क्या मायने हैं"
        topics.append(
            EditorialTopic(
                title=title,
                category=category,
                angle=angle,
                facts=FACT_BANK[key],
                public_questions=QUESTION_BANK[key],
                reference_name=reference_name,
                reference_url=reference_url,
            )
        )
    return topics


def build_long_form_article(topic: EditorialTopic):
    facts = "".join(f"<li>{fact}</li>" for fact in topic.facts)
    questions = "".join(f"<li>{question}</li>" for question in topic.public_questions)
    return f"""
<p><strong>{topic.title}</strong> आज के public-interest debate का महत्वपूर्ण हिस्सा है। यह लेख किसी पार्टी के प्रचार या विरोध के लिए नहीं, बल्कि पाठकों को मुद्दे की पृष्ठभूमि, असर और समाधान समझाने के लिए तैयार किया गया है। {topic.angle}</p>

<h2>मुद्दा क्यों महत्वपूर्ण है</h2>
<p>जब शिक्षा, परीक्षा, ईंधन नीति, रोजगार, आंदोलन या सार्वजनिक भरोसे से जुड़ा सवाल उठता है, तो उसका असर सिर्फ headline तक सीमित नहीं रहता। आम नागरिक यह देखता है कि सरकार, विभाग, संस्थाएं और राजनीतिक दल समस्या को कितनी गंभीरता से लेते हैं। इसी भरोसे पर लोकतांत्रिक माहौल, नीति की स्वीकार्यता और जनता की प्राथमिकताएं बनती हैं।</p>

<p>भारत जैसे बड़े देश में किसी भी बड़े फैसले या विवाद का असर अलग-अलग वर्गों पर अलग तरीके से पड़ता है। छात्र fairness चाहते हैं, अभिभावक सुरक्षा और भविष्य की चिंता करते हैं, उपभोक्ता खर्च और भरोसे को देखते हैं, और मतदाता जवाबदेही को महत्व देते हैं। इसलिए ऐसे विषयों पर संतुलित, तथ्य-आधारित और साफ भाषा में चर्चा जरूरी है।</p>

<h2>अब तक के प्रमुख तथ्य</h2>
<ul>{facts}</ul>

<h2>जनता क्या चाह सकती है</h2>
<p>लोग आम तौर पर तीन चीजें चाहते हैं: स्पष्ट जानकारी, समयबद्ध कार्रवाई और जवाबदेही। यदि मामला परीक्षा का है तो छात्र चाहते हैं कि मेहनत और merit सुरक्षित रहे। यदि मामला E20 जैसे ईंधन बदलाव का है तो वाहन मालिक भरोसेमंद technical guidance चाहते हैं। यदि मामला जनआंदोलन या राजनीति का है तो लोग चाहते हैं कि उनकी वास्तविक चिंता को सिर्फ पार्टी संघर्ष बनाकर न देखा जाए।</p>

<p>ऐसे माहौल में जनता उन नेताओं और दलों को महत्व दे सकती है जो समस्या को नारे में नहीं, समाधान में बदलने की क्षमता दिखाएं। केवल आरोप लगाने से भरोसा नहीं बनता; भरोसा तब बनता है जब नीति, timeline, monitoring और grievance redressal जनता के सामने साफ रखे जाते हैं।</p>

<h2>किन सवालों का जवाब जरूरी है</h2>
<ul>{questions}</ul>

<h2>नीति और प्रशासन के लिए सीख</h2>
<p>किसी भी public policy या परीक्षा व्यवस्था में prevention सबसे जरूरी है। गलती होने के बाद जांच और सजा जरूरी है, लेकिन उससे भी बेहतर है ऐसी प्रणाली बनाना जिसमें breach की संभावना कम हो। इसके लिए digital audit trail, independent security audit, limited access protocol, tamper-proof logistics, और हर स्तर पर जिम्मेदार अधिकारी की पहचान जरूरी होती है।</p>

<p>Communication भी उतना ही महत्वपूर्ण है। जब लोग सवाल पूछ रहे हों, तब चुप्पी अफवाहों को जगह देती है। संबंधित विभागों को FAQ, helpline, official updates और local-language explanations जारी करने चाहिए। इससे misinformation कम होती है और जनता को लगता है कि उसकी चिंता सुनी जा रही है।</p>

<h2>राजनीतिक असर क्या हो सकता है</h2>
<p>ऐसे मुद्दों का राजनीतिक असर सीधे-सीधे किसी एक पार्टी के पक्ष या विपक्ष में बताना जल्दबाजी होगा। लेकिन इतना स्पष्ट है कि युवा और middle-class मतदाता performance, fairness और transparency को अधिक गंभीरता से देख सकते हैं। जो भी दल शिक्षा, रोजगार, उपभोक्ता हित और public accountability पर ठोस roadmap देगा, उसे जनता में सुनवाई मिल सकती है।</p>

<p>जनता की प्राथमिकता बदलती रहती है, लेकिन भरोसा हमेशा central मुद्दा रहता है। यदि किसी व्यवस्था में बार-बार leak, confusion, cost concern या unclear communication दिखती है, तो लोग बदलाव, सुधार या stronger accountability की मांग कर सकते हैं।</p>

<h2>आगे क्या होना चाहिए</h2>
<p>आगे की दिशा में सरकार और संस्थाओं को measurable reforms पर ध्यान देना चाहिए। परीक्षा मामलों में secure paper chain, encrypted digital process, independent audit, quick complaint window और compensation framework जैसे उपाय मददगार हो सकते हैं। E20 जैसे नीति मामलों में vehicle-wise guidance, authorised service advisories, fuel quality monitoring और consumer awareness की जरूरत है।</p>

<p>सबसे अहम बात यह है कि जनता को भरोसा दिलाया जाए कि उसकी चिंता को सुना जा रहा है। जब policy facts, public communication और accountability साथ चलते हैं, तब विवाद कम होता है और व्यवस्था मजबूत होती है।</p>

<p><strong>Editorial note:</strong> यह लेख उपलब्ध आधिकारिक/सार्वजनिक संदर्भों और policy background के आधार पर स्वतंत्र रूप से लिखा गया है। इसमें किसी दूसरे प्रकाशन की भाषा या संरचना का उपयोग नहीं किया गया है। Reference: {topic.reference_name}.</p>
""".strip()
