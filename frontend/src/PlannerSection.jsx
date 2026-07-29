import { useMemo, useState } from "react";
import "./planner.css";

function readLocalState(date, items) {
  const initial = Object.fromEntries(
    items.map((item) => [item.id, Boolean(item.completed)])
  );
  if (typeof window === "undefined") {
    return initial;
  }
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(`morning-brief:${date}`) || "{}"
    );
    return { ...initial, ...stored };
  } catch {
    return initial;
  }
}

function saveLocalState(date, state) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(
      `morning-brief:${date}`,
      JSON.stringify(state)
    );
  } catch {
    // The self-contained HTML still works when storage is blocked.
  }
}

function Meta({ item }) {
  const values = [
    item.category,
    item.difficulty,
    item.duration_minutes ? `${item.duration_minutes} мин` : "",
    item.repetitions ? `${item.repetitions} повтор.` : ""
  ].filter(Boolean);

  if (!values.length) {
    return null;
  }

  return (
    <span className="planner-item-meta">
      {values.map((value) => (
        <span key={value}>{value}</span>
      ))}
    </span>
  );
}

function ItemGroup({
  title,
  subtitle,
  items,
  checked,
  onToggle,
  emptyText
}) {
  return (
    <article className="planner-group">
      <header className="planner-group-header">
        <div>
          <p>{subtitle}</p>
          <h3>{title}</h3>
        </div>
        <strong>{items.length}</strong>
      </header>

      {items.length ? (
        <ul className="planner-list">
          {items.map((item) => (
            <li
              className={checked[item.id] ? "is-complete" : ""}
              key={item.id}
            >
              <label>
                <input
                  checked={Boolean(checked[item.id])}
                  onChange={() => onToggle(item.id)}
                  type="checkbox"
                />
                <span className="planner-checkbox" aria-hidden="true" />
                <span className="planner-item-copy">
                  <strong>{item.title}</strong>
                  {item.details && <span>{item.details}</span>}
                  <Meta item={item} />
                </span>
              </label>
            </li>
          ))}
        </ul>
      ) : (
        <p className="planner-empty">{emptyText}</p>
      )}
    </article>
  );
}

export function PlannerSection({ data }) {
  const planner = data && typeof data === "object" ? data : null;
  const items = useMemo(
    () => [
      ...(planner?.tasks || []),
      ...(planner?.routines || []),
      ...(planner?.diction || [])
    ],
    [planner]
  );
  const [checked, setChecked] = useState(() =>
    planner ? readLocalState(planner.date, items) : {}
  );

  if (!planner) {
    return null;
  }

  const completed = items.filter((item) => checked[item.id]).length;
  const total = items.length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const previousPercent = planner.previous_total
    ? Math.round((planner.previous_completed / planner.previous_total) * 100)
    : 0;

  function toggle(itemId) {
    setChecked((current) => {
      const next = { ...current, [itemId]: !current[itemId] };
      saveLocalState(planner.date, next);
      return next;
    });
  }

  return (
    <section
      className="planner-extension"
      id="daily-plan"
      aria-labelledby="daily-plan-title"
    >
      <div className="planner-extension-inner">
        <header className="planner-title-row">
          <div>
            <p className="planner-kicker">Личный план</p>
            <h2 id="daily-plan-title">Задачи, ритм и дикция.</h2>
            <p className="planner-intro">
              Существующий Morning Brief остался прежним. Ниже — дополнительный
              рабочий блок на сегодня.
            </p>
          </div>

          <div
            className="planner-progress"
            aria-label={`Выполнено ${completed} из ${total}`}
          >
            <span>Прогресс дня</span>
            <strong>{percent}%</strong>
            <div className="planner-progress-track">
              <span style={{ width: `${percent}%` }} />
            </div>
            <small>
              {completed} из {total} · примерно{" "}
              {planner.stats?.duration_minutes || 0} минут
            </small>
          </div>
        </header>

        <div className="planner-metrics">
          <div>
            <span>Одноразовые</span>
            <strong>{planner.tasks?.length || 0}</strong>
          </div>
          <div>
            <span>Регулярные</span>
            <strong>{planner.routines?.length || 0}</strong>
          </div>
          <div>
            <span>Дикция</span>
            <strong>{planner.diction?.length || 0}</strong>
          </div>
          <div>
            <span>Вчера</span>
            <strong>
              {planner.previous_total ? `${previousPercent}%` : "—"}
            </strong>
          </div>
        </div>

        <div className="planner-grid">
          <ItemGroup
            title="Одноразовые задачи"
            subtitle="Фокус"
            items={planner.tasks || []}
            checked={checked}
            onToggle={toggle}
            emptyText="На сегодня одноразовых задач нет."
          />
          <ItemGroup
            title="Ежедневные действия"
            subtitle="Ритм"
            items={planner.routines || []}
            checked={checked}
            onToggle={toggle}
            emptyText="Регулярных действий на сегодня нет."
          />
          <ItemGroup
            title="Практика дикции"
            subtitle="Речь"
            items={planner.diction || []}
            checked={checked}
            onToggle={toggle}
            emptyText="Упражнения пока не добавлены."
          />
        </div>

        <footer className="planner-footer">
          <div>
            <strong>
              {planner.completion_mode === "notion"
                ? "Главные отметки сохраняются в Notion."
                : "Эти отметки сохраняются только в этом браузере."}
            </strong>
            <span>
              Один и тот же план не пересобирается при повторном запуске в
              течение дня.
            </span>
          </div>
          {planner.notion_url ? (
            <a
              href={planner.notion_url}
              target="_blank"
              rel="noreferrer"
            >
              Открыть страницу дня в Notion
            </a>
          ) : (
            <span className="planner-notion-disabled">
              Notion пока не подключён
            </span>
          )}
        </footer>

        {planner.warnings?.length > 0 && (
          <details className="planner-warnings">
            <summary>
              Предупреждения синхронизации: {planner.warnings.length}
            </summary>
            <ul>
              {planner.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </section>
  );
}
