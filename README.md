# NovaCraft Launcher 3.0 — Restyle

Оновлений лаунчер Minecraft Java Edition для Windows на CustomTkinter. Збережено модулі Microsoft OAuth, встановлення версій і запуск гри з початкового проєкту; додано профілі, налаштування RAM та менеджер модів.

## Можливості
- Microsoft OAuth із PKCE через наявний `auth.py` (потрібен власний Azure Client ID і дозвіл Minecraft API).
- Офлайн-режим для одиночної гри та серверів `online-mode=false`.
- Профілі: назва, версія, папка гри та RAM. Профілі зберігаються в `%APPDATA%\\MyCraftLauncher\\settings.json`.
- Вибір виділення пам'яті 1–16 GB на головній сторінці (захист у коді дозволяє 1–32 GB).
- Менеджер модів: показує `.jar` і перемикає стан перейменуванням у `.jar.disabled`. Це просте керування файлами, не каталог для завантаження модів.
- Оновлений темний інтерфейс із фіолетовими акцентами, новою навігацією та переробленою головною сторінкою; фонова інсталяція та прогрес.

## Встановлення
Потрібен Python 3.11+.
```powershell
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Microsoft OAuth
1. Створи застосунок у Microsoft Entra/Azure з підтримкою Personal Microsoft accounts.
2. Додай платформу Public client/native та redirect URI `http://localhost:53682`.
3. Увімкни public client flows і вкажи Application (client) ID у `config.py` або змінній середовища `MYCRAFT_CLIENT_ID`.
4. Новим Azure-застосункам може знадобитися схвалення Minecraft API: https://aka.ms/mce-reviewappid.

Пароль Microsoft лаунчер не отримує. Початковий `storage.py` зберігає refresh-токен у `account.json` звичайним текстом у профілі Windows; не передавай цей файл іншим людям.

## Профілі та моди
Профіль зберігає власні версію, папку гри та RAM. Для справді ізольованих модів створи окрему папку гри для кожного профілю. У меню «Моди» файли `.jar` можна вимкнути/увімкнути без видалення. Перевіряй сумісність модів із версією Minecraft і завантажувачем (Fabric/Forge) вручну.

## Збірка EXE
```powershell
pyinstaller --noconsole --onefile --name MyCraftLauncher --collect-all minecraft_launcher_lib --collect-all customtkinter main.py
```
Спершу налаштуй `CLIENT_ID` у `config.py`. Для розповсюдження не вбудовуй приватні секрети; OAuth public client не повинен містити client secret.

## Примітки
- Розмір RAM має бути меншим за доступну системну пам'ять; не виділяй грі всю RAM.
- Реальна сумісність параметра JVM залежить від версії `minecraft-launcher-lib`. Якщо версія бібліотеки не передає `jvmArguments`, налаштування RAM не застосовуватиметься; перевір лог запуску та актуальну документацію бібліотеки.
- Для Fabric/Forge спочатку встанови відповідний loader у вибрану папку гри. Менеджер модів не встановлює самі loaders.
