import "./App.css";

const HERO_MARKUP_IMAGE_PATH = "../frontend/public/hero-bg.jpg";
const HERO_CSS_IMAGE_PATH = "../public/hero-bg.jpg";
const PUBLIC_HERO_IMAGE_PATH = "/hero-bg.jpg";

const emptyData = {
  date: "",
  city: "Светлогорск",
  country: "Беларусь",
  weather: {
    temperature: "не удалось получить данные",
    description: "неизвестно",
    items: []
  },
  holidays: {
    summary: "праздников нет",
    items: []
  },
  cats: [],
  tasks: [],
  assets: {
    heroImage: ""
  }
};

const WEEKDAYS_RU = [
  "воскресенье",
  "понедельник",
  "вторник",
  "среда",
  "четверг",
  "пятница",
  "суббота"
];

const INFORMAL_REASONS = [
  "день сделать одно важное дело без спешки",
  "день спокойного утра",
  "день маленького личного ритуала",
  "день закрыть один небольшой хвост",
  "день выбрать свой тихий повод"
];

function valueFor(items, label) {
  const item = items.find((entry) => entry.label.toLowerCase() === label.toLowerCase());
  return item?.value || "не удалось получить данные";
}

function cleanImageUrl(src) {
  return String(src || HERO_CSS_IMAGE_PATH)
    .replace(/\\/g, "/")
    .replace(/"/g, "%22");
}

function imageStack(src) {
  return `url("${cleanImageUrl(toCssImagePath(src))}")`;
}

function isFileOutput() {
  return typeof window !== "undefined" && window.location.protocol === "file:";
}

function getHeroCssImagePath() {
  if (isFileOutput()) {
    return HERO_CSS_IMAGE_PATH;
  }

  return PUBLIC_HERO_IMAGE_PATH;
}

function getHeroMarkupImagePath() {
  if (typeof window !== "undefined" && window.location.protocol === "file:") {
    return HERO_MARKUP_IMAGE_PATH;
  }

  return PUBLIC_HERO_IMAGE_PATH;
}

function toCssImagePath(src) {
  const value = src || getHeroCssImagePath();

  if (isFileOutput() && String(value).startsWith("cats/")) {
    return `../../output/${value}`;
  }

  if (isFileOutput() && value === HERO_MARKUP_IMAGE_PATH) {
    return HERO_CSS_IMAGE_PATH;
  }

  return value;
}

function taskCountText(count) {
  const mod10 = count % 10;
  const mod100 = count % 100;

  if (mod10 === 1 && mod100 !== 11) {
    return `${count} задача`;
  }

  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return `${count} задачи`;
  }

  return `${count} задач`;
}

function weekdayForDate(dateText) {
  const [year, month, day] = String(dateText || "")
    .split("-")
    .map((part) => Number.parseInt(part, 10));

  if (!year || !month || !day) {
    return "";
  }

  return WEEKDAYS_RU[new Date(year, month - 1, day).getDay()];
}

function informalReasonForDate(dateText) {
  const day = Number.parseInt(String(dateText || "").slice(-2), 10);
  const index = Number.isFinite(day) ? day % INFORMAL_REASONS.length : 0;
  return INFORMAL_REASONS[index];
}

function sentenceCase(value) {
  if (!value) {
    return "";
  }

  return `${value[0].toUpperCase()}${value.slice(1)}`;
}

function cityForIntro(city) {
  if (city === "Светлогорск") {
    return "Светлогорске";
  }

  return city;
}

function BlurTitle({ lines }) {
  return (
    <h1 className="hero-title" aria-label={lines.join(" ")}>
      {lines.map((line, index) => (
        <span
          aria-hidden="true"
          className="hero-title-line"
          key={line}
          style={{ "--word-delay": `${180 + index * 150}ms` }}
        >
          {line}
        </span>
      ))}
    </h1>
  );
}

function MetricRow({ label, value }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DetailRows({ rows }) {
  return (
    <dl className="detail-rows">
      {rows.map(([label, value]) => (
        <div className="detail-row" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function TaskList({ tasks }) {
  if (!tasks.length) {
    return (
      <div className="task-detail-copy">
        <p className="detail-note">Свободный день. Красиво.</p>
        <p className="source-note">Источник задач: tasks.md</p>
      </div>
    );
  }

  return (
    <div className="task-detail-copy">
      <ul className="task-lines">
        {tasks.map((task) => (
          <li key={task}>{task}</li>
        ))}
      </ul>
      <p className="source-note">Источник задач: tasks.md</p>
    </div>
  );
}

export function App({ data = emptyData }) {
  const brief = { ...emptyData, ...data };
  const weather = { ...emptyData.weather, ...brief.weather };
  const holidays = { ...emptyData.holidays, ...brief.holidays };
  const cats = Array.isArray(brief.cats) ? brief.cats : [];
  const tasks = Array.isArray(brief.tasks) ? brief.tasks : [];
  const weatherItems = Array.isArray(weather.items) ? weather.items : [];
  const assets = { ...emptyData.assets, ...(brief.assets || {}) };
  const taskCount = tasks.length;
  const taskSummary = taskCountText(taskCount);
  const taskPreview = tasks.slice(0, 3);
  const catImages = cats.map((cat) => cat.src || cat.url).filter(Boolean);
  const heroCssImagePath = getHeroCssImagePath();
  const heroMarkupImagePath = assets.heroImage || getHeroMarkupImagePath();
  const featureImage = catImages[0] || heroMarkupImagePath;
  const moodImage = catImages[1] || catImages[0] || heroCssImagePath;
  const description = weather.description || "неизвестно";
  const feelsLike = valueFor(weatherItems, "Ощущается как");
  const wind = valueFor(weatherItems, "Ветер");
  const precipitation = valueFor(weatherItems, "Осадки");
  const rain = valueFor(weatherItems, "Дождь");
  const hasHolidays = Boolean(holidays.items?.length);
  const holidayText = hasHolidays ? holidays.items.join(", ") : "нет";
  const informalReason = informalReasonForDate(brief.date);
  const holidaySentence = hasHolidays
    ? `Официальные праздники: ${holidays.items.join(", ")}.`
    : `Официальных праздников сегодня нет, поэтому можно выбрать свой маленький повод.`;
  const weekday = weekdayForDate(brief.date);
  const introOpening = [sentenceCase(weekday) || "Сегодня", cityForIntro(brief.city)]
    .filter(Boolean)
    .join(" в ");
  const displayDate = [weekday, brief.date].filter(Boolean).join(", ");

  const weatherRows = [
    ["Температура", weather.temperature],
    ["Ощущается как", feelsLike],
    ["Ветер", wind],
    ["Осадки", precipitation],
    ["Дождь", rain],
    ["Описание", description]
  ];

  return (
    <main className="terrain-page">
      <section className="terrain-hero" id="today">
        <img className="terrain-hero-image" src={heroMarkupImagePath} alt="" aria-hidden="true" />

        <nav className="terrain-nav animate-nav" aria-label="Навигация сводки">
          <a className="nav-capsule" href="#today">
            Сводка готова
          </a>
          <span className="nav-wordmark">Утро</span>
          <a className="nav-capsule nav-capsule-right" href="#details">
            Детали
          </a>
        </nav>

        <div className="hero-content">
          <p className="hero-kicker animate-fade-up delay-1">
            {brief.city} · {weekday || "сегодня"}
          </p>
          <BlurTitle lines={["СВОДКА", "НА ДЕНЬ"]} />
          <p className="hero-subtitle animate-fade-up delay-4">
            Погода, коты и миссии дня — спокойно собраны в одном месте.
          </p>
          <p className="hero-meta animate-fade-up delay-5">
            {brief.country} · {displayDate} · {weather.temperature}
          </p>
        </div>
      </section>

      <section className="today-editorial" aria-labelledby="today-heading">
        <div className="editorial-grid">
          <figure className="feature-card animate-fade-up">
            <img src={featureImage} alt="Кот дня" />
            <figcaption className="feature-info">
              <MetricRow label="Температура" value={weather.temperature} />
              <MetricRow label="Ветер" value={wind} />
              <MetricRow label="Задачи" value={taskSummary} />
            </figcaption>
          </figure>

          <article className="editorial-copy">
            <p className="section-label">Сегодня</p>
            <h2 id="today-heading">Почему этот день имеет форму.</h2>
            <p className="editorial-lede">
              {introOpening}: {description}, {weather.temperature}. {holidaySentence} В
              фокусе — {taskSummary}.
            </p>

            <div className="metric-list" aria-label="Краткие метрики дня">
              <MetricRow label="Погода" value={`${weather.temperature} · ${description}`} />
              <MetricRow label="Праздники" value={holidayText} />
              <MetricRow label="Миссии" value={taskSummary} />
            </div>
          </article>
        </div>
      </section>

      <section className="modules-section" aria-labelledby="modules-heading">
        <div className="section-heading">
          <p className="section-label">Сводка</p>
          <h2 id="modules-heading">Модули дня</h2>
        </div>

        <div className="module-card-grid">
          <a
            className="daily-module-card weather-module-card"
            href="#weather-details"
          >
            <div className="module-card-content">
              <p>Погода сейчас</p>
              <h3>ПОГОДА</h3>
              <span>{weather.temperature} · {description}</span>
              <em>Ощущается как {feelsLike}; ветер {String(wind).toLowerCase()}.</em>
            </div>
          </a>

          <a
            className="daily-module-card cats-module-card"
            id="cats"
            href="#cats"
            style={{ "--card-image": imageStack(moodImage) }}
          >
            <div className="module-card-content">
              <p>Кот дня</p>
              <h3>КОТЫ</h3>
              <span>+10 к настроению</span>
            </div>
          </a>

          <a
            className="daily-module-card tasks-module-card"
            href="#tasks"
          >
            <div className="module-card-content">
              <p>Фокус дня</p>
              <h3>МИССИИ</h3>
              <span>{taskSummary}</span>
              {taskPreview.length > 0 && (
                <ul className="module-task-preview">
                  {taskPreview.map((task) => (
                    <li key={task}>{task}</li>
                  ))}
                </ul>
              )}
            </div>
          </a>
        </div>
      </section>

      <section className="details-section" id="details" aria-labelledby="details-heading">
        <div className="details-inner">
          <div className="details-heading">
            <p className="section-label">Детали сводки</p>
            <h2 id="details-heading">Детали сводки</h2>
          </div>

          <article className="detail-panel" id="weather-details">
            <header>
              <span>01</span>
              <h3>Погода</h3>
            </header>
            <DetailRows rows={weatherRows} />
          </article>

          <article className="detail-panel" id="holiday-details">
            <header>
              <span>02</span>
              <h3>Праздники</h3>
            </header>
            {hasHolidays ? (
              <ul className="holiday-lines">
                {holidays.items.map((holiday) => (
                  <li key={holiday}>{holiday}</li>
                ))}
              </ul>
            ) : (
              <div className="detail-copy">
                <p>Официальных праздников сегодня нет.</p>
                <p>
                  <span className="informal-label">Маленький повод дня</span>
                  {informalReason}.
                </p>
              </div>
            )}
          </article>

          <article className="detail-panel" id="tasks">
            <header>
              <span>03</span>
              <h3>Задачи</h3>
            </header>
            <TaskList tasks={tasks} />
          </article>
        </div>
      </section>
    </main>
  );
}
