# application

Application-слой управляет use cases и pipeline.

Здесь находятся сценарии анализа сообщения, сбор dataset record, export dataset и отправка feedback.

Application зависит от ports/interfaces, а не от конкретных реализаций.
