# AgentCAD

**AgentCAD** — експериментальний агент для автоматичного створення 3D-моделей у **FreeCAD** за текстовим описом конструкції.

Користувач задає форму, розміри та конструктивні елементи деталі природною мовою. Агент за допомогою **LangChain** і LLM генерує Python-скрипт FreeCAD, перевіряє його, запускає через `FreeCADCmd`, аналізує результат виконання та, у разі помилки, автоматично намагається виправити код. Для роботи через браузер передбачено **Streamlit**-інтерфейс з журналом виконання, переглядом згенерованого коду та інтерактивною 3D-візуалізацією STL.

---

## 1. Основні можливості

Поточна версія AgentCAD підтримує:

- введення текстового опису деталі українською або іншою мовою;
- використання LLM через:
  - OpenRouter;
  - OpenAI;
- генерацію повного Python-скрипта для FreeCAD;
- структурований результат LLM через `Pydantic`;
- базову статичну перевірку безпеки згенерованого коду;
- перевірку синтаксису Python;
- запуск скрипта через `FreeCADCmd` / `freecadcmd`;
- перехоплення `stdout`, `stderr` та коду завершення FreeCAD;
- автоматичне повторне генерування/виправлення скрипта після помилки;
- збереження всіх спроб генерації та журналів;
- експорт моделей у:
  - `FCStd`;
  - `STL`;
  - `STEP/STP`;
- Streamlit-інтерфейс;
- інтерактивний перегляд STL через Plotly;
- відображення:
  - кількості трикутників STL;
  - габаритів X × Y × Z;
  - площі поверхні;
  - розміру файла;
- завантаження створених CAD-файлів через вебінтерфейс;
- регулювання висоти 3D-перегляду;
- підготовлене Conda-середовище з `LangGraph` для подальшого розвитку проєкту.

---

## 2. Архітектура

Поточна версія використовує простий агентний цикл:

```text
Текстовий опис конструкції
          │
          ▼
      Streamlit
          │
          ▼
       LangChain
          │
          ▼
          LLM
          │
          ▼
  Python-код для FreeCAD
          │
          ▼
  Static validation
          │
          ▼
   Python syntax check
          │
          ▼
      FreeCADCmd
          │
     ┌────┴─────┐
     │          │
   успіх      помилка
     │          │
     │          ▼
     │      stdout/stderr
     │          │
     │          ▼
     │     повторний запит
     │          до LLM
     │          │
     └──────────┘
          │
          ▼
 FCStd / STL / STEP
          │
          ▼
  Streamlit + Plotly
```

Головний цикл можна коротко описати як:

```text
generate → validate → execute → inspect → repair
```

На цьому етапі цикл реалізований звичайним Python-кодом. `LangGraph` уже входить до Conda-середовища та планується для наступної версії.

---

## 3. Структура проєкту

Рекомендована структура каталогу:

```text
AgentCAD/
├── freecad_langchain_agent.py
├── streamlit_agentcad_v3.py
├── agentcad_environment_streamlit.yml
├── README.md
├── .env
└── agentcad_runs/
```

### `freecad_langchain_agent.py`

Основний агент.

Виконує:

1. отримання текстового опису;
2. підключення до LLM;
3. формування LangChain prompt;
4. отримання структурованого результату;
5. збереження Python-коду;
6. перевірку коду;
7. запуск `FreeCADCmd`;
8. аналіз помилок;
9. повторну генерацію коду;
10. збереження фінального результату.

### `streamlit_agentcad_v3.py`

Вебінтерфейс AgentCAD.

Містить:

- поле введення запиту;
- налаштування LLM;
- вибір максимальної кількості спроб;
- параметр timeout;
- налаштування висоти 3D-перегляду;
- live-вивід роботи агента;
- вкладки:
  - **3D STL**;
  - **Результат**;
  - **FreeCAD-код**;
  - **Журнал**;
  - **Файли**;
- інтерактивний STL viewer на Plotly;
- завантаження результатів.

За бажанням файл можна перейменувати:

```bash
mv streamlit_agentcad_v3.py streamlit_agentcad.py
```

### `agentcad_environment_streamlit.yml`

Conda-середовище для CLI-агента, Streamlit та майбутніх LangGraph-агентів.

---

## 4. Вимоги

### Операційна система

Основний сценарій розробки орієнтований на Linux.

### Необхідне ПЗ

- Conda / Miniconda / Anaconda;
- Python 3.11 у Conda-середовищі;
- FreeCAD, встановлений у системі;
- доступ до LLM API:
  - OpenRouter або
  - OpenAI.

Важливо: FreeCAD **не імпортується у Python Conda-середовища**.

AgentCAD запускає зовнішню програму:

```text
FreeCADCmd
```

або:

```text
freecadcmd
```

Тому FreeCAD використовує власне Python-середовище.

---

## 5. Перевірка FreeCAD

Перевірте, чи доступний консольний FreeCAD:

```bash
which FreeCADCmd
```

або:

```bash
which freecadcmd
```

Перевірка запуску:

```bash
FreeCADCmd --version
```

або:

```bash
freecadcmd --version
```

Якщо команда розташована нестандартно, її можна явно задати через `.env`:

```dotenv
FREECAD_CMD=/повний/шлях/до/freecadcmd
```

---

## 6. Створення Conda-середовища

Перейдіть у каталог проєкту:

```bash
cd /path/to/AgentCAD
```

Створіть середовище:

```bash
conda env create -f agentcad_environment_streamlit.yml
```

Активуйте його:

```bash
conda activate agentcad
```

Перевірте:

```bash
python --version
```

Очікується Python 3.11.

Перевірка Streamlit:

```bash
streamlit --version
```

Перевірка основних Python-пакетів:

```bash
python -c "import langchain, langgraph, streamlit, plotly, stl; print('OK')"
```

---

## 7. Оновлення існуючого середовища

Якщо `agentcad` уже створено:

```bash
conda activate agentcad
```

Потім:

```bash
conda env update \
    -n agentcad \
    -f agentcad_environment_streamlit.yml \
    --prune
```

---

## 8. Python-залежності

Файл середовища містить:

```yaml
name: agentcad
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - pip:
      - langchain
      - langchain-openai
      - langchain-openrouter
      - langgraph
      - streamlit
      - python-dotenv
      - pydantic
      - numpy
      - numpy-stl
      - plotly
      - orjson
```

---

## 9. Налаштування `.env`

Створіть файл:

```text
.env
```

у кореневій директорії проєкту.

### Варіант OpenRouter

```dotenv
OPENROUTER_API_KEY=sk-or-v1-ВАШ_КЛЮЧ

LLM_PROVIDER=openrouter
LLM_MODEL=openai/gpt-5.5
```

За необхідності:

```dotenv
FREECAD_CMD=/usr/bin/freecadcmd
```

### Варіант OpenAI

```dotenv
OPENAI_API_KEY=ВАШ_КЛЮЧ

LLM_PROVIDER=openai
LLM_MODEL=gpt-5.5
```

### Важливо

Не додавайте `.env` до Git.

Рекомендований `.gitignore`:

```gitignore
.env
agentcad_runs/
__pycache__/
*.pyc
```

---

## 10. Запуск CLI-агента

Найпростіший запуск:

```bash
conda activate agentcad
python freecad_langchain_agent.py
```

Після цього буде запропоновано ввести опис:

```text
Опишіть деталь, її форму та розміри.
>
```

Наприклад:

```text
Створи прямокутну пластину розміром 80×40×3 мм.
Зроби чотири наскрізні отвори діаметром 4 мм.
Центри отворів розташуй на відстані 7 мм від країв.
```

---

## 11. Передавання запиту через командний рядок

```bash
python freecad_langchain_agent.py \
  --description "Створи циліндр діаметром 40 мм, висотою 20 мм, з центральним наскрізним отвором діаметром 8 мм"
```

Із явним вибором провайдера та моделі:

```bash
python freecad_langchain_agent.py \
  --provider openrouter \
  --model openai/gpt-5.5 \
  --description "Створи пластину 100×50×4 мм з чотирма отворами діаметром 5 мм"
```

---

## 12. Основні аргументи CLI

```text
--description
```

Текстовий опис конструкції.

```text
--provider
```

Провайдер:

```text
openrouter
openai
```

```text
--model
```

Назва LLM.

```text
--output-dir
```

Каталог результатів.

```text
--max-attempts
```

Максимальна кількість генерацій/виправлень.

За замовчуванням:

```text
3
```

```text
--temperature
```

Температура LLM.

За замовчуванням:

```text
0.0
```

```text
--timeout
```

Максимальний час виконання FreeCAD-скрипта.

За замовчуванням:

```text
180 секунд
```

```text
--freecad-cmd
```

Явний шлях до `FreeCADCmd`.

```text
--unsafe
```

Вимикає базову статичну перевірку згенерованого коду.

Використовувати лише у контрольованому середовищі.

---

## 13. Запуск Streamlit

Активуйте середовище:

```bash
conda activate agentcad
```

Запустіть останню версію:

```bash
streamlit run streamlit_agentcad_v3.py
```

Якщо файл перейменовано:

```bash
streamlit run streamlit_agentcad.py
```

Streamlit зазвичай відкриє:

```text
http://localhost:8501
```

---

## 14. Робота зі Streamlit

### 14.1. Введення конструкції

У полі запиту можна написати, наприклад:

```text
Створи прямокутну пластину 80×40×3 мм.
Зроби чотири наскрізні отвори діаметром 4 мм.
Центри отворів розташуй на відстані 7 мм від найближчих країв.
Заокругли зовнішні кути радіусом 3 мм.
```

Streamlit автоматично додає технічну вимогу:

- створити STL;
- зберегти FCStd;
- за можливості створити STEP;
- експортувати саме фінальну геометрію.

Це необхідно для 3D-перегляду результату.

### 14.2. Бічна панель

Доступні параметри:

- LLM provider;
- модель;
- максимальна кількість спроб;
- timeout FreeCAD;
- висота 3D-перегляду;
- шлях до скрипта агента;
- шлях до `FreeCADCmd`;
- коренева директорія запусків.

### 14.3. Висота STL viewer

3D-вікно має регульовану висоту.

Типове значення:

```text
480 px
```

Для екранів 1080p рекомендовано:

```text
420–500 px
```

Масштабування колесом миші вимкнено, щоб Plotly не блокував вертикальну прокрутку сторінки.

---

## 15. Вкладки Streamlit

### `3D STL`

Показує інтерактивну STL-модель.

Можна:

- обертати модель;
- змінювати ракурс;
- масштабувати засобами Plotly;
- вибирати STL, якщо їх декілька.

Також відображаються:

```text
кількість трикутників
X × Y × Z
площа поверхні
розмір STL
```

Під моделлю доступний компактний список створених файлів.

### `Результат`

Містить:

- вихідний запит;
- короткий опис моделі, сформований LLM;
- кількість створених STL;
- кількість STEP/STP;
- кількість FCStd.

### `FreeCAD-код`

Показує фінальний успішний Python-скрипт.

Основний файл:

```text
generated_freecad_model.py
```

### `Журнал`

Показує:

- live-вивід AgentCAD;
- `stdout`;
- `stderr`;
- журнали окремих запусків FreeCAD.

### `Файли`

Містить усі результати поточного запуску та дозволяє завантажити їх.

---

## 16. Каталог результатів

Streamlit створює для кожного запиту окремий каталог:

```text
agentcad_runs/
├── run_20260809_150001_123456/
├── run_20260809_150233_654321/
└── ...
```

Приклад вмісту:

```text
run_20260809_150001_123456/
├── generated_attempt_1.py
├── freecad_attempt_1.log
├── generated_attempt_2.py
├── freecad_attempt_2.log
├── generated_freecad_model.py
├── model.FCStd
├── model.step
└── model.stl
```

---

## 17. Механізм генерації FreeCAD-коду

LangChain формує prompt, що містить:

```text
MODE
USER DESCRIPTION
OUTPUT DIRECTORY
PREVIOUS SCRIPT
FREECAD EXECUTION DIAGNOSTICS
```

На першій спробі:

```text
MODE = INITIAL GENERATION
```

На наступних:

```text
MODE = REPAIR AFTER FAILED EXECUTION
```

Таким чином LLM отримує не лише початкове завдання, а й:

- попередню версію коду;
- traceback;
- stdout/stderr;
- код завершення FreeCAD.

---

## 18. Structured Output

LLM повертає дані через Pydantic-модель:

```python
class GeneratedFreeCADScript(BaseModel):
    summary: str
    script_code: str
```

Отже AgentCAD отримує окремо:

```python
generated.summary
generated.script_code
```

Це надійніше, ніж витягувати Python-код із довільного текстового повідомлення.

---

## 19. Правила генерації FreeCAD

System prompt рекомендує використовувати:

```python
import FreeCAD as App
import Part
```

та уникати GUI-залежностей:

```python
FreeCADGui
```

Оскільки код виконується через headless FreeCAD.

Згенерований скрипт повинен:

1. створити документ;
2. побудувати геометрію;
3. виконати `doc.recompute()`;
4. зберегти документ;
5. експортувати необхідні формати;
6. після успіху вивести:

```text
AGENTCAD_SUCCESS
```

---

## 20. Як визначається успішне виконання

AgentCAD перевіряє одночасно:

```text
FreeCAD return code == 0
```

і наявність:

```text
AGENTCAD_SUCCESS
```

і відсутність:

```text
Traceback (most recent call last)
```

Лише при виконанні всіх умов спроба вважається успішною.

---

## 21. Автоматичне виправлення помилок

Приклад:

LLM згенерувала:

```python
Part.makeBoxx(80, 40, 3)
```

FreeCAD повернув:

```text
AttributeError:
module 'Part' has no attribute 'makeBoxx'
```

AgentCAD передає LLM:

```text
PREVIOUS SCRIPT:
...

FREECAD EXECUTION DIAGNOSTICS:
AttributeError...
```

LLM генерує нову версію:

```python
Part.makeBox(80, 40, 3)
```

Після цього FreeCAD запускається повторно.

---

## 22. Статична перевірка безпеки

Перед виконанням AgentCAD аналізує Python AST.

Блокуються деякі потенційно небезпечні модулі, наприклад:

```python
subprocess
socket
requests
httpx
urllib
ftplib
paramiko
ctypes
multiprocessing
```

Також блокуються окремі виклики:

```python
eval()
exec()
compile()
__import__()
```

та системні команди типу:

```python
os.system()
os.popen()
shutil.rmtree()
```

---

## 23. Важливе обмеження безпеки

Поточна перевірка — це **не повноцінна sandbox-ізоляція**.

LLM генерує код, який реально виконується через FreeCAD на комп'ютері.

Тому поточна версія призначена насамперед для:

- локальної роботи;
- експериментів;
- контрольованого середовища;
- одного довіреного користувача.

Для публічного вебсервісу рекомендовано виконувати `FreeCADCmd` у контейнері, наприклад:

```text
Streamlit
    │
    ▼
Agent service
    │
    ▼
Docker container
    │
    ├── FreeCADCmd
    ├── isolated workdir
    ├── CPU limit
    ├── RAM limit
    └── network disabled
```

---

## 24. Типові проблеми

### FreeCADCmd не знайдено

Помилка:

```text
FreeCAD command-line executable was not found
```

Перевірте:

```bash
which freecadcmd
```

та задайте:

```dotenv
FREECAD_CMD=/usr/bin/freecadcmd
```

---

### API key не знайдено

Для OpenRouter:

```text
OPENROUTER_API_KEY is not set
```

Додайте до `.env`:

```dotenv
OPENROUTER_API_KEY=...
```

Для OpenAI:

```dotenv
OPENAI_API_KEY=...
```

---

### STL не відображається

Перевірте вкладку:

```text
Журнал
```

та переконайтеся, що FreeCAD успішно створив `.stl`.

Streamlit автоматично додає до запиту вимогу експорту STL, але генерація може завершитися раніше через помилку FreeCAD.

---

### Сторінка погано прокручується біля 3D-моделі

У поточній версії:

```python
scrollZoom=False
```

Колесо миші використовується для прокрутки сторінки.

Висоту 3D-вікна можна зменшити у бічній панелі.

---

### Генерація займає багато часу

Час складається з:

```text
LLM generation
+
FreeCAD execution
+
можливі повторні LLM generation
+
можливі повторні FreeCAD execution
```

Зменшити час можна через:

- швидшу LLM;
- `max_attempts=1–2`;
- спрощення конструкції;
- зменшення складності boolean-операцій.

---

## 25. Поточні обмеження

Поточний AgentCAD:

- не перевіряє геометричну відповідність моделі початковому тексту;
- не аналізує STL через computer vision;
- не має окремого geometry planner;
- не має довготривалої пам'яті;
- не використовує LangGraph для керування станом;
- не має human-in-the-loop підтвердження перед запуском коду;
- не виконує автоматичну перевірку технологічності 3D-друку;
- не виконує FEM-аналіз;
- не працює у контейнерній sandbox за замовчуванням.

---

## 26. Наступний етап — LangGraph

Поточний Python-цикл:

```text
generate
   ↓
validate
   ↓
execute
   ↓
error?
 ┌─┴─┐
no  yes
│    │
END  repair
      │
      └──→ validate
```

доцільно перенести у LangGraph.

Можлива архітектура:

```text
START
  │
  ▼
AnalyzeRequest
  │
  ▼
GeometryPlanner
  │
  ▼
GenerateFreeCADCode
  │
  ▼
ValidateCode
  │
  ▼
RunFreeCAD
  │
  ├──── success ────► InspectGeometry
  │                       │
  │                       ▼
  │                    Export
  │                       │
  │                       ▼
  │                      END
  │
  └──── error ──────► AnalyzeError
                          │
                          ▼
                      RepairCode
                          │
                          └────► ValidateCode
```

---

## 27. Можливий стан LangGraph

```python
class AgentCADState(TypedDict):
    description: str

    geometry_plan: str
    generated_code: str

    attempt: int

    freecad_stdout: str
    freecad_stderr: str
    return_code: int

    success: bool

    fcstd_file: str | None
    step_file: str | None
    stl_file: str | None
```

---

## 28. Перспективні агенти

У складнішій версії AgentCAD можна виділити:

```text
GeometryPlanner
       ↓
DimensionChecker
       ↓
FreeCADCodeGenerator
       ↓
CodeValidator
       ↓
FreeCADExecutor
       ↓
GeometryInspector
       ↓
ManufacturabilityChecker
       ↓
ExportAgent
```

Окремий `GeometryInspector` може перевіряти:

- габарити STL;
- кількість тіл;
- замкненість mesh;
- наявність отворів;
- мінімальну товщину;
- відповідність заданим розмірам.

---

## 29. Подальший розвиток

Можливі напрями:

1. перехід на LangGraph;
2. окремий geometry planner;
3. збереження стану агента;
4. історія діалогів;
5. редагування вже створеної моделі природною мовою;
6. завантаження існуючого FCStd;
7. автоматична перевірка STL;
8. рендеринг з декількох ракурсів;
9. порівняння текстового завдання з геометрією;
10. Docker sandbox;
11. параметричні моделі;
12. бібліотека шаблонів CAD-операцій;
13. підтримка Assembly;
14. підготовка моделей до багатокольорового 3D-друку;
15. автоматичний аналіз технологічності;
16. інтеграція FEM;
17. генерація креслень;
18. експорт технічного звіту.

---

## 30. Швидкий старт

```bash
# 1. Перейти у каталог
cd /path/to/AgentCAD

# 2. Створити середовище
conda env create -f agentcad_environment_streamlit.yml

# 3. Активувати
conda activate agentcad

# 4. Створити .env
nano .env

# 5. Перевірити FreeCAD
which freecadcmd

# 6. Запустити Streamlit
streamlit run streamlit_agentcad_v3.py
```

Після цього відкрити:

```text
http://localhost:8501
```

і ввести, наприклад:

```text
Створи круглий диск діаметром 60 мм і товщиною 4 мм.
У центрі зроби наскрізний отвір діаметром 8 мм.
Додай чотири отвори діаметром 4 мм на колі діаметром 40 мм.
```

---

## 31. Статус проєкту

AgentCAD наразі є **експериментальним прототипом**.

Поточна версія демонструє працездатну інтеграцію:

```text
Natural Language
      ↓
LangChain
      ↓
LLM
      ↓
FreeCAD Python
      ↓
FreeCADCmd
      ↓
STL / STEP / FCStd
      ↓
Streamlit + Plotly
```

Головна мета поточного етапу — перевірити можливість автоматичного переходу від природномовного опису конструкції до реально виконуваного CAD-скрипта з автоматичним аналізом і виправленням помилок.
