"""Hebrew test lines for the Hebrew benchmark (2026-10-17, glyph sweep: "If you manage to finish latin ... proceed
with Hebrew letters"). Everyday words without vowel points, every letter and all five final forms, short lines of
words with ordinary punctuation. No digits: a line mixing right-to-left words and left-to-right numbers needs the
bidi algorithm, which the renderer does not run.
"""
import numpy as np

WORDS = """
שלום בית ספר ילד ילדה אבא אמא מים לחם חלב עיר רחוב חנות כסף זמן יום לילה בוקר ערב שנה חודש שבוע עבודה משפחה
חבר חברה מורה תלמיד כיתה שולחן כיסא דלת חלון מכונית אוטובוס רכבת דרך ים הר עץ פרח שמש ירח כוכב גשם רוח אש אור
חושך קפה תה סוכר מלח ביצה גבינה עוף דג פרי תפוח בננה ענב ירק עגבנייה מלפפון גזר בצל שום אורז מרק ארוחה מטבח
חדר מיטה ספה טלפון מחשב מכתב עיתון שאלה תשובה סיפור שיר מוזיקה משחק כדור רופא חולה בריא גדול קטן טוב רע חדש
ישן יפה חם קר מהר לאט הרבה מעט כאן שם עכשיו אחר כל גם רק עוד כבר אולי תמיד פעם הולך הולכת בא באה אוכל שותה
קורא כותב רואה שומע אומר יודע רוצה צריך יכול אוהב עושה נותן לוקח קונה מוכר פותח סוגר יושב עומד קם חושב מבין
זוכר שוכח מחפש מוצא עוזר מחכה מתחיל גומר צוחק בוכה נוסע טס שוחה רץ צפון דרום מזרח מערב ירושלים חיפה צפת אילת
נמל שוק קניון בנק דואר משטרה מספר חשבון קבלה הזמנה מחיר הנחה צהריים שבת חג פסח סוכה ציפור צב זאב פיל נמר קוף
כלב חתול סוס פרה כבש עז תרנגול ברווז פרפר דבורה ארץ מלך קפץ חוץ סוף אף נוף לך שלך שלכם אצלך עליך ממך כמוך
""".split()
PUNCT = ["", "", "", ".", ",", "?", "!", ":"]


def lines(n: int, seed: int = 2027) -> list[str]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        ws = [str(w) for w in rng.choice(WORDS, rng.integers(3, 6))]
        if rng.random() < 0.3:
            k = int(rng.integers(0, len(ws) - 1))
            ws[k] += ","
        if rng.random() < 0.1:
            k = int(rng.integers(0, len(ws)))
            ws[k] = '"' + ws[k] + '"'
        out.append(" ".join(ws) + str(rng.choice(PUNCT)))
    return out


if __name__ == "__main__":
    ls = lines(300)
    print("\n".join(ls[:5]))
    letters = set("".join(ls))
    print("letters missing:", [chr(c) for c in range(0x5D0, 0x5EB) if chr(c) not in letters])
