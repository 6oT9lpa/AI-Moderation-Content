from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel


def build_hard_eval_pack() -> list[dict]:
    rows = [
        *_safe_cases()[:20],
        *_scam_cases(),
        *_nsfw_cases(),
        *_toxic_cases(),
        *_hate_cases(),
        *_threat_cases(),
        *_invite_cases(),
        *_spam_cases(),
        *_advertisement_cases(),
        *_url_cases(),
        *_evasion_cases(),
    ]
    if len(rows) != 100:
        raise RuntimeError(f"hard eval pack must contain 100 rows, got {len(rows)}")
    return rows


def _row(text: str, primary: ModerationLabel, labels: list[ModerationLabel]) -> dict:
    return {
        "text": text,
        "primary_label": primary.value,
        "labels": [label.value for label in labels],
    }


def _safe_cases() -> list[dict]:
    label = ModerationLabel.SAFE
    return [
        _row("чек пек", label, [label]),
        _row("твоя сестренка была у меня дома, мы вместе делали проект", label, [label]),
        _row("твоя сестренка была у меня дома", label, [label]),
        _row("твоя сестра была у меня дома", label, [label]),
        _row("твоя младшая сестра была у меня дома", label, [label]),
        _row("твоя сестра была у меня дома с родителями и забрала учебник", label, [label]),
        _row("ты уважаешь свою маму? я тоже уважаю родителей и говорю спокойно", label, [label]),
        _row("мамке привет это сокращение mq, объясняю сленг без оскорбления", label, [label]),
        _row("гей это нейтральное слово, если мы обсуждаем ориентацию без оскорблений", label, [label]),
        _row("в книге герой попал в рабство, мы обсуждаем сюжет без оскорблений", label, [label]),
        _row("раздача денег звучит как скам, поэтому не переходим по ссылкам", label, [label]),
        _row("steam просит подтвердить вход только в официальном клиенте", label, [label]),
        _row("посмотрите документацию github.com/example/project", label, [label]),
        _row("моей сестре 12 лет и она ищет безопасный сервер для игры", label, [label]),
        _row("отрывок из классической книги про семью, дом и уважение к матери", label, [label]),
        _row("не отправляйте никому коды из смс это опасно", label, [label]),
        _row("обсуждаем как отличать розыгрыш от мошенничества", label, [label]),
        _row("сегодня встречаемся в голосовом канале в восемь", label, [label]),
        _row("моя сестренка была у меня дома весь вечер, играли в настолки", label, [label]),
        _row("проверяем домен steamcommunity.com и объясняем признаки фишинга", label, [label]),
        _row("пример фразы получи 5000 руб нужен для датасета", label, [label]),
        _row("цитирую сообщение нарушителя для жалобы модератору", label, [label]),
        _row("в рассказе герой вернулся домой к сестре и принес ей книги", label, [label]),
    ]


def _scam_cases() -> list[dict]:
    label = ModerationLabel.SCAM
    url = ModerationLabel.URL
    return [
        _row("https://не-пиздешь.ру хей ребята тут раздача бабла", label, [label, url]),
        _row("https://не-пиздешь.ру хей ребята тут раздача денег", label, [label, url]),
        _row("https://не-пиздешь.ру раздача денег каждому за регу 5000", label, [label, url]),
        _row("https://steam.resolv.com тут раздают бесплатные скины в кс", label, [label, url]),
        _row("steam.resolv.com free skins для кс, войди через steam и подтверди трейд", label, [label, url]),
        _row("discord-nitro.gift.example забери нитро после входа в аккаунт", label, [label, url]),
        _row("sber-bonus.example выплата 5000 каждому, подтверди карту", label, [label, url]),
        _row("официальный steamcommunity подарок но ссылка steamcomrnunity-login.example", label, [label, url]),
        _row("получи 10000 руб на карту напиши код из смс", label, [label]),
        _row("выиграл подарок забери приз по ссылке", label, [label, url]),
    ]


def _nsfw_cases() -> list[dict]:
    label = ModerationLabel.NSFW
    toxic = ModerationLabel.TOXIC
    url = ModerationLabel.URL
    return [
        _row("ты уважаешь свою маму? а я люблю ей давать в рот", label, [label, toxic]),
        _row("твоя мама вроде серьезная женщина, но я бы ей дал в рот", label, [label, toxic]),
        _row("передай маме что я люблю такие разговоры в рот", label, [label, toxic]),
        _row("тут ебут телок", label, [label, toxic]),
        _row("тут малолетних девочек", label, [label]),
        _row("тут ебут малолетних сучек", label, [label, toxic]),
        _row("тут ебут малолетних телочек, подписывайся и будешь ебать 12 летнюю шлюху", label, [label, toxic]),
        _row("закрытый канал с малолетними девочками, ссылка в профиле", label, [label, url]),
        _row("твоя 12 летная сестренка была у меня в сексуальном рабстве", label, [label, toxic]),
        _row("приватный nsfw канал только сегодня", label, [label]),
    ]


def _toxic_cases() -> list[dict]:
    label = ModerationLabel.TOXIC
    return [
        _row("слыш мусор", label, [label]),
        _row("слыш не пизди мне тут", label, [label]),
        _row("мать шлюха", label, [label]),
        _row("друг у тебя мать шлюха", label, [label]),
        _row("дура ебанная", label, [label]),
        _row("mq тебе, мамке привет после такого мува", label, [label]),
        _row("мп твоей мамке, играть ты явно не умеешь", label, [label]),
        _row("какой же ты тупой, опять все испортил", label, [label]),
        _row("лох уйди отсюда", label, [label]),
        _row("ты вообще ничего не понимаешь уходи отсюда", label, [label]),
    ]


def _hate_cases() -> list[dict]:
    label = ModerationLabel.HATE
    toxic = ModerationLabel.TOXIC
    return [
        _row("фу чел выйди с дс, ты же гомик", label, [label, toxic]),
        _row("хай мен ты долго в доту для гомосексуалов не играл, да ведь", label, [label, toxic]),
        _row("таких геев как ты надо держать подальше от нашего сервера", label, [label, toxic]),
        _row("лгбт игрокам тут не рады, уходи из канала", label, [label]),
        _row("ало горный житель, сын пидораса", label, [label, toxic]),
        _row("ало сын пидора", label, [label, toxic]),
        _row("пидр", label, [label, toxic]),
        _row("ненавижу всех мигрантов на сервере", label, [label]),
        _row("таких людей надо выгнать с сервера только за ориентацию", label, [label]),
        _row("гомосексуалам здесь не место, пусть уходят", label, [label]),
    ]


def _threat_cases() -> list[dict]:
    label = ModerationLabel.THREAT
    toxic = ModerationLabel.TOXIC
    return [
        _row("я найду тебя после игры", label, [label]),
        _row("убью тебя если еще раз напишешь", label, [label, toxic]),
        _row("солью твой адрес в чат", label, [label]),
        _row("доксну тебя и всем покажу данные", label, [label]),
        _row("твоя сестренка была у меня в рабстве, так что думай как говорить", label, [label, toxic]),
        _row("я знаю где живет твоя сестра и могу сделать так что она пропадет", label, [label]),
        _row("если зайдешь в канал, найду твою семью и солью все данные", label, [label]),
        _row("сломаю тебе лицо после катки", label, [label, toxic]),
        _row("жди меня у подъезда, поговорим так что запомнишь", label, [label]),
        _row("твоей семье лучше не знать что я могу сделать", label, [label]),
    ]


def _invite_cases() -> list[dict]:
    label = ModerationLabel.INVITE
    url = ModerationLabel.URL
    return [
        _row("заходи к нам https://discord.gg/freeboost", label, [label, url]),
        _row("новый сервер discord.com/invite/room123 всем сюда", label, [label, url]),
        _row("инвайт в приватный канал discord.gg/qwerty", label, [label, url]),
        _row("го на другой сервер, ссылка discord.gg/test", label, [label, url]),
        _row("не реклама, но все переходите в наш дискорд discord.gg/hidden", label, [label, url]),
        _row("переехали на новый discord invite в описании", label, [label]),
    ]


def _spam_cases() -> list[dict]:
    label = ModerationLabel.SPAM
    ad = ModerationLabel.ADVERTISEMENT
    return [
        _row("ЗАЛЕТАЙ СРОЧНО ПОЛУЧИ БОНУС БОНУС БОНУС", label, [label]),
        _row("@everyone @everyone срочно все сюда быстро быстро быстро", label, [label]),
        _row("скидка скидка скидка только сегодня переходи", label, [label, ad]),
        _row("оооооооооооооооооооооооооооооооооооооо", label, [label]),
        _row("пиши в лс всем раздам промокод быстро быстро быстро", label, [label, ad]),
        _row("обычное сообщение бонус бонус бонус бонус бонус бонус бонус", label, [label]),
    ]


def _advertisement_cases() -> list[dict]:
    label = ModerationLabel.ADVERTISEMENT
    return [
        _row("купите аккаунты дешево доставка моментально", label, [label]),
        _row("продам буст сервера гарантия цена в лс", label, [label]),
        _row("магазин скинов открыт переходи за прайсом", label, [label]),
        _row("делаю оформление профиля и аватарки за рубли", label, [label]),
        _row("кому нужен донат дешевле официального магазина, пишите плюс", label, [label]),
        _row("закажи прокачку аккаунта до вечера, цена ниже", label, [label]),
    ]


def _url_cases() -> list[dict]:
    label = ModerationLabel.URL
    return [
        _row("посмотри мой репозиторий https://github.com/example/project", label, [label]),
        _row("видео лежит на youtube.com/watch?v=abc", label, [label]),
        _row("документация на docs.python.org/3/library/re.html", label, [label]),
        _row("картинка в cdn.discordapp.com/attachments/1/2/image.gif", label, [label]),
        _row("новость на example.org/news без призов и регистраций", label, [label]),
        _row("официальная страница steamcommunity.com/profiles/123", label, [label]),
    ]


def _evasion_cases() -> list[dict]:
    label = ModerationLabel.EVASION
    scam = ModerationLabel.SCAM
    toxic = ModerationLabel.TOXIC
    return [
        _row("пoлучи бoнус cрoчнo", label, [label, scam]),
        _row("дeбuл написано смешанными буквами", label, [label, toxic]),
        _row("cooбщeниe c латинскими символами внутри слов", label, [label]),
        _row("бoнуc нa cepвepe написан похожими буквами", label, [label]),
        _row("oчeнь мнoгo cимвoлoв пoxoжe нa pyccкиe", label, [label]),
        _row("нaпиши мнe в лc тeкcт cмешaнный", label, [label]),
    ]
