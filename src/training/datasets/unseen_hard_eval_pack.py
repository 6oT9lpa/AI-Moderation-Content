from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel


def build_unseen_hard_eval_pack() -> list[dict]:
    rows = [
        *_safe_cases(),
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
        raise RuntimeError(f"unseen hard eval pack must contain 100 rows, got {len(rows)}")
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
        _row("твоя сестренка заходила ко мне домой за тетрадью и сразу ушла", label, [label]),
        _row("моя мама была у вас дома на собрании родителей", label, [label]),
        _row("брат оставил у меня дома зарядку, передай ему пожалуйста", label, [label]),
        _row("сестра приходила в гости с родителями и помогла с проектом", label, [label]),
        _row("мы обсуждаем в книге сцену возвращения сына к матери", label, [label]),
        _row("у героя романа мать ждала его дома весь вечер", label, [label]),
        _row("папа просил передать, что завтра встреча у школы", label, [label]),
        _row("родители забрали документы и спокойно ушли домой", label, [label]),
        _row("у меня дома была семейная встреча, поэтому я не играл", label, [label]),
        _row("сестренка попросила помочь ей с математикой после уроков", label, [label]),
        _row("мама сказала не переходить по подозрительным ссылкам", label, [label]),
        _row("мы проверяем примеры токсичности для обучения модерации", label, [label]),
        _row("слово рабство обсуждается в историческом контексте урока", label, [label]),
        _row("гей как нейтральный термин в статье не является оскорблением", label, [label]),
        _row("steamcommunity.com открылся как официальный профиль без призов", label, [label]),
        _row("github.com/org/repo это ссылка на исходники бота", label, [label]),
        _row("раздача денег в примере указана как типичный признак скама", label, [label]),
        _row("цитату нарушителя отправили модератору как доказательство", label, [label]),
        _row("младшая сестра была у меня дома вместе с нашей мамой", label, [label]),
        _row("семья героя пришла домой после долгой дороги", label, [label]),
    ]


def _scam_cases() -> list[dict]:
    label = ModerationLabel.SCAM
    url = ModerationLabel.URL
    return [
        _row("steamcornmunity-login.example просит войти и забрать подарок", label, [label, url]),
        _row("получи 5000 после регистрации, карту привяжи по ссылке", label, [label, url]),
        _row("твой аккаунт заблокируют, подтверди пароль на vk-help-login.example", label, [label, url]),
        _row("скины уже ждут, войди через стим и подтверди обмен", label, [label]),
        _row("discord nitro бесплатно только сегодня, введи токен аккаунта", label, [label]),
        _row("sber-pay-prize.example обещает выплату после ввода кода из смс", label, [label, url]),
        _row("официальный розыгрыш, но домен похож на steamcommunnity", label, [label, url]),
        _row("забери робуксы после ввода логина и пароля", label, [label]),
        _row("тебе пришла компенсация, укажи карту и cvv для проверки", label, [label]),
        _row("faceit-drop-login.example раздает ножи за авторизацию steam", label, [label, url]),
    ]


def _nsfw_cases() -> list[dict]:
    label = ModerationLabel.NSFW
    toxic = ModerationLabel.TOXIC
    return [
        _row("я бы твоей маме такое в личке написал, что тебе стыдно станет", label, [label, toxic]),
        _row("обсуждение стало сексуальным и направлено на родственницу собеседника", label, [label]),
        _row("скинь интимные фото, никто кроме нас не увидит", label, [label]),
        _row("приватный канал с откровенным контентом, вход по заявке", label, [label]),
        _row("пошлые намеки на сестру собеседника продолжаются весь чат", label, [label, toxic]),
        _row("канал с взрослыми фото без предупреждения в общем чате", label, [label]),
        _row("пишет непристойные предложения матери игрока", label, [label, toxic]),
        _row("в голосовом начали описывать интимные действия", label, [label]),
        _row("отправь нюдсы за роль на сервере", label, [label]),
        _row("он завуалированно домогается до родственницы участника", label, [label, toxic]),
    ]


def _toxic_cases() -> list[dict]:
    label = ModerationLabel.TOXIC
    return [
        _row("слышь отход, ты опять все испортил", label, [label]),
        _row("уйди из чата, от тебя только проблемы", label, [label]),
        _row("ты позор сервера и играть не умеешь", label, [label]),
        _row("мусорный мув, больше не заходи", label, [label]),
        _row("мамке привет за такого игрока", label, [label]),
        _row("ты просто бесполезный тип", label, [label]),
        _row("закрой чат и не мешай нормальным людям", label, [label]),
        _row("опять этот клоун все слил", label, [label]),
        _row("тебя никто тут не ждет, свали", label, [label]),
        _row("научись читать, прежде чем писать", label, [label]),
    ]


def _hate_cases() -> list[dict]:
    label = ModerationLabel.HATE
    toxic = ModerationLabel.TOXIC
    return [
        _row("таким геям не место в нашем канале", label, [label, toxic]),
        _row("выгоните его за ориентацию, нечего ему тут сидеть", label, [label]),
        _row("мигрантам на сервере делать нечего", label, [label]),
        _row("людей этой национальности надо банить сразу", label, [label]),
        _row("лгбт игроки пусть уходят на другой сервер", label, [label]),
        _row("сын пидора опять пишет в чат", label, [label, toxic]),
        _row("таких как ты по вере тут терпеть не будут", label, [label]),
        _row("женщинам тут не место, пусть молчат", label, [label]),
        _row("ненавижу всех таких, они портят игру", label, [label]),
        _row("ориентация у тебя причина выйти с сервера", label, [label]),
    ]


def _threat_cases() -> list[dict]:
    label = ModerationLabel.THREAT
    toxic = ModerationLabel.TOXIC
    return [
        _row("я подожду тебя после игры и объясню лично", label, [label]),
        _row("твой адрес уже почти нашел, дальше сам поймешь", label, [label]),
        _row("еще одно сообщение и твоей семье будет плохо", label, [label]),
        _row("увижу тебя у подъезда и разговор будет короткий", label, [label]),
        _row("солью твои данные в общий чат", label, [label]),
        _row("я знаю где учится твоя сестра", label, [label]),
        _row("после катки найду тебя без свидетелей", label, [label]),
        _row("сломаю тебе аккаунт и покажу всем переписки", label, [label]),
        _row("убью за такой мув, отвечаю", label, [label, toxic]),
        _row("не пиши больше, иначе пожалеешь", label, [label]),
    ]


def _invite_cases() -> list[dict]:
    label = ModerationLabel.INVITE
    url = ModerationLabel.URL
    return [
        _row("наш новый сервер тут discord.gg/newhome", label, [label, url]),
        _row("все переходим в другой дискорд, инвайт в профиле", label, [label]),
        _row("discord.com/invite/private заходи в закрытый канал", label, [label, url]),
        _row("не пишите тут, продолжение на моем сервере", label, [label]),
        _row("кто хочет роль, переходите по инвайту в описании", label, [label]),
        _row("ссылка на новый дс появится через минуту", label, [label]),
    ]


def _spam_cases() -> list[dict]:
    label = ModerationLabel.SPAM
    ad = ModerationLabel.ADVERTISEMENT
    return [
        _row("срочно срочно срочно все сюда быстро быстро", label, [label]),
        _row("@everyone бонус бонус бонус забираем сейчас", label, [label]),
        _row("пиши плюс плюс плюс плюс плюс кто хочет", label, [label]),
        _row("аааааааааааааааааааааааааааааааааааааа", label, [label]),
        _row("скидка скидка скидка магазин открыт", label, [label, ad]),
        _row("повторяю третий раз переходите переходите переходите", label, [label]),
    ]


def _advertisement_cases() -> list[dict]:
    label = ModerationLabel.ADVERTISEMENT
    return [
        _row("продам буст сервера дешево, писать в личку", label, [label]),
        _row("магазин аккаунтов открыт, гарантия до вечера", label, [label]),
        _row("оформлю аватарку за рубли, примеры в профиле", label, [label]),
        _row("купите донат дешевле официального магазина", label, [label]),
        _row("делаю прокачку ранга, цена ниже рынка", label, [label]),
        _row("продаю приватный софт для игры, оплата картой", label, [label]),
    ]


def _url_cases() -> list[dict]:
    label = ModerationLabel.URL
    return [
        _row("документация лежит на docs.python.org", label, [label]),
        _row("репозиторий github.com/example/moderator обновили", label, [label]),
        _row("видео матча youtube.com/watch?v=test", label, [label]),
        _row("официальный профиль steamcommunity.com/id/player", label, [label]),
        _row("картинка загружена на cdn.discordapp.com/attachments/file.png", label, [label]),
        _row("новость без призов и регистрации на example.org/news", label, [label]),
    ]


def _evasion_cases() -> list[dict]:
    label = ModerationLabel.EVASION
    scam = ModerationLabel.SCAM
    toxic = ModerationLabel.TOXIC
    return [
        _row("пoлучи бoнyc за peгиcтpaцию", label, [label, scam]),
        _row("дeбuл написано через смешанные символы", label, [label, toxic]),
        _row("cpoчнo зaбepи пpиз", label, [label, scam]),
        _row("мyсop ты опять cлил", label, [label, toxic]),
        _row("бoнyc нa кapтy пocлe cмc", label, [label, scam]),
        _row("cooбщeниe специально смешивает латиницу и кириллицу", label, [label]),
    ]
