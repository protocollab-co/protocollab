```markdown
# ADR 005: Архитектура ProtoCollab и абстракция репозитория

## Статус

Предложено

## Дата

2026-04-17

## Автор

@cherninkiy

## Принимающие решение

Сопровождающие Protocollab

## Контекст


 [ADR 004](004_YAML_Transformation_Library_RU.md) утвердил `yaml_transformer` как основополагающую библиотеку для YAML-трансформаций (слияние, фильтрация, патчинг, копирование с учётом `!include` и т.д.). На основе этого мультиагентная система (спецификатор, оптимизатор, тестировщик, слиятель, рецензент, генератор) требует **высокоуровневого слоя оркестрации**, предоставляющего унифицированный API для агентов и пользователей для взаимодействия с репозиторием YAML-спецификаций.

Этот слой, названный **ProtoCollab**, должен:

- Абстрагироваться от различных бэкендов хранения (локальный Git, in‑memory, простые файлы), чтобы агенты могли работать со спецификациями независимо от их местонахождения.
- Интегрировать `yaml_transformer` для всех операций, специфичных для YAML (слияние, diff, патчинг).
- Предоставлять операции контроля версий (коммит, переключение, история) через единообразный интерфейс.
- Поддерживать коллаборативный рабочий процесс, в котором несколько агентов предлагают и сливают изменения.

Проект находится на ранней стадии; допустимы критические изменения. Нам необходимо определить архитектуру ProtoCollab и абстракцию репозитория, лежащую в её основе.

## Решение

Мы создадим новый подпакет **`protocollab.yaml_repository`**, который определяет абстрактный интерфейс `RepositoryBackend` и включает легковесные эталонные реализации. Слой оркестрации ProtoCollab будет частью основного пакета `protocollab` и будет зависеть от `yaml_transformer` и `yaml_repository`.

### Структура пакетов

Все новые модули будут располагаться в `src/protocollab/` рядом с существующими модулями CLI, загрузчика и генераторов:

```
src/protocollab/
├── __init__.py                     # экспортирует ProtoCollab, create_repository_backend
├── cli/                            # существующий CLI
├── loader/                         # существующий загрузчик
├── validator/                      # существующий валидатор
├── generators/                     # существующие генераторы
├── agent/                          # будущие реализации агентов
└── yaml_repository/                # новый подпакет
    ├── __init__.py                 # экспортирует RepositoryBackend, ManualBackend, MultiAgentBackend
    ├── base.py                     # абстрактный RepositoryBackend
    ├── manual.py                   # ManualBackend
    ├── multi_agent.py              # MultiAgentBackend (в памяти, для тестирования)
    ├── gitpy/                      # GitPyRepository (бэкенд на gitpython)
    │   └── __init__.py
    └── gitcli/                     # GitCliRepository (бэкенд на subprocess)
        └── __init__.py
```

**Примечание:** Pro-бэкенды (`github`, `sqlite`, `rag`) **не** включены в публичный open‑source репозиторий. Они будут разрабатываться и распространяться отдельно под коммерческой лицензией.

### Цепочка зависимостей

```
protocollab
├── yaml_transformer → yaml_serializer
└── yaml_repository (ядро)
    ├── gitpy (опционально, требует gitpython)
    └── gitcli (без дополнительных зависимостей)
```

### Интерфейс RepositoryBackend

Абстрактный класс определяет контракт для версионированного хранения YAML-спецификаций.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
from datetime import datetime

@dataclass
class Ref:
    name: str           # например, "main", "feature/xyz"
    commit_hash: str    # полный SHA

@dataclass
class FileInfo:
    path: Path
    ref: Ref
    last_modified: datetime
    size: int

@dataclass
class Change:
    path: Path
    status: str         # "added", "modified", "deleted", "renamed"
    old_path: Optional[Path] = None

@dataclass
class CommitInfo:
    hash: str
    author: str
    message: str
    timestamp: datetime
    parent_hashes: List[str]
    changes: List[Change]

class RepositoryBackend(ABC):
    """Абстрактный интерфейс для версионированного хранилища YAML-спецификаций."""

    # ---- Базовые операции с файлами ----
    @abstractmethod
    def read_file(self, path: Path, ref: Optional[str] = None) -> str:
        """Прочитать содержимое файла по указанной ссылке (HEAD если None)."""
        pass

    @abstractmethod
    def stage_file(self, path: Path, content: str) -> None:
        """Добавить файл в индекс для следующего коммита. Сам коммит не создаётся."""
        pass

    @abstractmethod
    def unstage_file(self, path: Path) -> None:
        """Убрать файл из индекса."""
        pass

    @abstractmethod
    def commit(self, message: str, author: str) -> CommitInfo:
        """Создать коммит из всех проиндексированных изменений."""
        pass

    @abstractmethod
    def delete_file(self, path: Path, message: str, author: str) -> CommitInfo:
        """Удалить файл и закоммитить удаление (атомарное удобство)."""
        pass

    @abstractmethod
    def exists(self, path: Path, ref: Optional[str] = None) -> bool:
        """Проверить существование файла по указанной ссылке."""
        pass

    @abstractmethod
    def list_files(self, directory: Optional[Path] = None, ref: Optional[str] = None) -> List[Path]:
        """Рекурсивно перечислить все YAML-файлы в директории (корень если None)."""
        pass

    # ---- Операции контроля версий ----
    @abstractmethod
    def get_current_ref(self) -> Ref:
        """Вернуть текущую ссылку HEAD."""
        pass

    @abstractmethod
    def checkout(self, ref_name: str, create: bool = False) -> Ref:
        """
        Переключиться на ветку/тег/коммит.
        Если `create` истинно, создать новую ветку с именем `ref_name` от текущего HEAD.
        """
        pass

    @abstractmethod
    def get_commit_history(
        self, ref: Optional[str] = None, path: Optional[Path] = None, max_count: int = 100
    ) -> List[CommitInfo]:
        """Получить историю коммитов, опционально отфильтрованную по пути."""
        pass

    @abstractmethod
    def diff(self, ref1: str, ref2: str, path: Optional[Path] = None) -> str:
        """Унифицированный diff между двумя ссылками."""
        pass

    @abstractmethod
    def merge_base(self, ref1: str, ref2: str) -> Ref:
        """Найти лучшего общего предка двух ссылок."""
        pass

    @abstractmethod
    def get_blob(self, ref: str, path: Path) -> str:
        """Получить содержимое файла точно в том виде, как оно сохранено в коммите."""
        pass

    @abstractmethod
    def get_root_directory(self) -> Path:
        """Абсолютный путь к корню репозитория в локальной файловой системе."""
        pass

    @abstractmethod
    def resolve_ref(self, ref_name: str) -> Ref:
        """Преобразовать строковое имя (ветка, тег, SHA) в объект Ref."""
        pass
```

**API индексации (staging)**: Разделение `stage_file` / `commit` позволяет атомарно записывать несколько файлов одним коммитом, что важно для рабочих процессов агентов.

### Конкретные бэкенды

| Бэкенд | Расположение | Назначение | Зависимости | Примечания |
|--------|--------------|------------|-------------|------------|
| `ManualBackend` | `yaml_repository.manual` | Простая файловая система **без** версионирования. Каждый `stage_file` + `commit` просто перезаписывает файл. Методы вроде `checkout`, `merge_base`, `diff` выбрасывают `NotImplementedError`. | Нет | Публичный, для простого локального использования или тестирования. |
| `MultiAgentBackend` | `yaml_repository.multi_agent` | Хранилище в памяти, полностью реализующее версионирование. Полезно для тестирования многоагентной коллаборации без обращения к диску. | Нет | Публичный, для модульных и интеграционных тестов. |
| `GitPyRepository` | `yaml_repository.gitpy` | Локальный Git-репозиторий с использованием библиотеки `gitpython`. | `gitpython` | Публичный (extra `gitpy`). |
| `GitCliRepository` | `yaml_repository.gitcli` | Локальный Git-репозиторий с вызовами `git` через `subprocess`. | Системный Git | Публичный (extra `gitcli`). |

**Pro-бэкенды**: `GitHubRepository`, `SqliteRepository` и `RagRepository` считаются Pro-функциями. Их исходный код **не** будет включён в публичный репозиторий. Open‑source пакет `protocollab` может выдавать понятную ошибку при попытке их инстанцирования, направляя пользователя к получению Pro-лицензии.

### Высокоуровневый API ProtoCollab

Пакет `protocollab` предоставит класс `ProtoCollab`, оркестрирующий рабочие процессы агентов:

```python
from protocollab.yaml_transformer import MergeStrategy, MergeResult

class ProtoCollab:
    def __init__(self, backend: RepositoryBackend):
        self.backend = backend

    def merge_refs(self, ref1: str, ref2: str, strategy: MergeStrategy) -> MergeResult:
        """Трёхстороннее слияние двух ссылок с использованием yaml_transformer."""
        base_ref = self.backend.merge_base(ref1, ref2)
        base_doc = self._load_spec(base_ref.commit_hash)
        left_doc = self._load_spec(ref1)
        right_doc = self._load_spec(ref2)
        return merge(base_doc, left_doc, right_doc, strategy)

    def apply_patch(self, ref: str, patches: List[Dict], message: str, author: str) -> CommitInfo:
        """Применить JSON Patch к спецификации и закоммитить."""
        ...

    def checkout_branch(self, branch_name: str, create: bool = True) -> Ref:
        ...

    # … другие удобные методы
```

Агенты (спецификатор, оптимизатор и др.) будут использовать этот API вместо прямого манипулирования файлами.

### Интеграция с `yaml_transformer`

ProtoCollab полагается на `yaml_transformer` для:

- Трёхстороннего слияния (`merge`)
- Сравнения (`diff`)
- Применения JSON Patch (`patch`)
- Копирования документов между бэкендами (например, flatten для передачи агенту)

`MultiAgentBackend` также может внутренне использовать `yaml_transformer` для симуляции конфликтов слияния при тестировании.

### Фабричная функция

В `protocollab` будет предоставлена фабрика для создания подходящего бэкенда:

```python
def create_repository_backend(backend_type: str, **kwargs) -> RepositoryBackend:
    """
    Создать бэкенд репозитория.

    backend_type может быть:
        "manual"  → ManualBackend(root_path)
        "multi_agent" → MultiAgentBackend()
        "gitpy"   → GitPyRepository(repo_path)
        "gitcli"  → GitCliRepository(repo_path)

    Pro-бэкенды ('github', 'sqlite', 'rag') недоступны в Community Edition.
    """
```

## Последствия

### Положительные

- **Разделение ответственности**: Логика хранения отделена от YAML-трансформаций и оркестрации агентов.
- **Подключаемость**: Новые бэкенды (например, S3, etcd) можно добавлять без изменения ядра ProtoCollab.
- **Тестируемость**: `MultiAgentBackend` позволяет быстро и изолированно тестировать коллаборацию агентов.
- **Чёткие границы open‑source**: Pro-функции исключены из публичного репозитория, что снижает юридическую сложность и затраты на сопровождение.

### Отрицательные

- `ManualBackend` нарушает полный контракт `RepositoryBackend` (выбрасывает `NotImplementedError`). Это осознанный компромисс ради простоты; пользователи, нуждающиеся в полном версионировании, должны использовать Git-бэкенд.
- Некоторые бэкенды (особенно `GitCliRepository`) требуют аккуратной обработки вывода подпроцессов и ошибок.
- API индексации (staging) вносит больше сложности, чем простой `write_file`, но он необходим для атомарных многофайловых коммитов.

### Смягчение

- Сохранять основной интерфейс `RepositoryBackend` минимальным и стабильным.
- Чётко документировать, какие методы не поддерживаются `ManualBackend`.
- Использовать `extras` в `pyproject.toml` для явного указания опциональных зависимостей.

## План реализации

### Фаза 1: Ядро подпакета `yaml_repository`
1. Создать `src/protocollab/yaml_repository/` с `base.py`, `manual.py` и `multi_agent.py`.
2. Написать исчерпывающие модульные тесты с использованием `MultiAgentBackend`.
3. Обеспечить совместимость с валидацией `root_dir` из `yaml_serializer`.
4. Выпустить как часть ядра `protocollab`.

### Фаза 2: Git-бэкенды
1. Реализовать `GitPyRepository` в `yaml_repository/gitpy/`.
2. Реализовать `GitCliRepository` в `yaml_repository/gitcli/`.
3. Добавить `gitpython` как опциональный extra.
4. Протестировать на реальных Git-репозиториях.

### Фаза 3: Слой оркестрации ProtoCollab
1. Разработать класс `ProtoCollab` в `protocollab/collab.py`.
2. Интегрировать с `yaml_transformer`.
3. Добавить команды CLI для рабочих процессов, управляемых агентами (например, `pc agent run`).

### Фаза 4: Pro-бэкенды (отдельный график)
1. Разработать `GitHubRepository`, `SqliteRepository` и `RagRepository` в приватном репозитории.
2. Распространять под коммерческой лицензией.

## Рассмотренные альтернативы

- **Встраивание логики репозитория непосредственно в `ProtoCollab`** – отвергнуто, так как это жёстко закодировало бы предположения о хранилище и затруднило тестирование.
- **Единый `write_file`, всегда создающий коммит** – отвергнуто, так как многофайловые изменения обычны в рабочих процессах агентов и должны быть атомарными.
- **Использование `pygit2` вместо `gitpython`** – `pygit2` является более низкоуровневой привязкой; `gitpython` предоставляет более Pythonic API и достаточен для наших нужд.
- **Включение Pro-бэкендов в open‑source репозиторий с проверкой лицензии** – отвергнуто из-за накладных расходов на сопровождение и юридической ясности; чистое разделение предпочтительнее.

## Ссылки

- [ADR 004: Библиотека трансформации YAML и архитектура ProtoCollab](004_YAML_Transformation_Library_RU.md)
- [Документация GitPython](https://gitpython.readthedocs.io/)
- [Документация GitHub REST API](https://docs.github.com/en/rest)
