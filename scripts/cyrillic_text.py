"""Russian test lines for the Cyrillic benchmark (2026-10-17): everyday words covering all 33 letters, a capital at
the start of each line and now and then a word in capitals, ordinary punctuation, some numbers."""
import numpy as np

WORDS = """
дом книга мама папа вода хлеб молоко город улица магазин деньги время день ночь утро вечер год месяц неделя работа
семья друг подруга учитель ученик класс стол стул дверь окно машина автобус поезд дорога море гора дерево цветок
солнце луна звезда дождь ветер огонь свет кофе чай сахар соль яйцо сыр курица рыба фрукт яблоко банан овощ помидор
огурец морковь лук рис суп обед кухня комната кровать диван телефон компьютер письмо газета вопрос ответ история
песня музыка игра мяч врач больной здоровый большой маленький хороший плохой новый старый красивый жаркий холодный
быстро медленно много мало здесь там сейчас всегда тоже только уже ещё может идёт читает пишет видит слышит говорит
знает хочет может любит делает даёт берёт покупает продаёт открывает закрывает сидит стоит спит думает понимает помнит
ищет находит помогает ждёт начинает смеётся плачет едет летит плывёт бежит север юг восток запад Москва Киев Минск
порт рынок банк почта полиция номер счёт чек заказ цена скидка щука щётка объём подъезд съезд въезд мышь ёж ёлка
юбка юг яма язык эхо этаж цирк цифра жук жизнь шум шапка фильм фото чашка час йогурт край мой твой бой
""".split()
PUNCT = ["", "", ".", ",", "?", "!", ":"]


def lines(n: int, seed: int = 2028) -> list[str]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        ws = [str(w) for w in rng.choice(WORDS, rng.integers(3, 6))]
        ws[0] = ws[0][0].upper() + ws[0][1:]
        if rng.random() < 0.2:
            k = int(rng.integers(0, len(ws)))
            ws[k] = ws[k].upper()
        if rng.random() < 0.2:
            ws.insert(int(rng.integers(1, len(ws) + 1)), str(rng.integers(1, 1000)))
        if rng.random() < 0.3:
            ws[int(rng.integers(0, len(ws) - 1))] += ","
        out.append(" ".join(ws) + str(rng.choice(PUNCT)))
    return out


if __name__ == "__main__":
    ls = lines(300)
    print("\n".join(ls[:5]))
    have = set("".join(ls))
    print("missing:", [chr(c) for c in list(range(0x410, 0x450)) + [0x401, 0x451] if chr(c) not in have])
