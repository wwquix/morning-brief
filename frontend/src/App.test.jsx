import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App.jsx";

const embedded = { heroImage: "data:image/png;base64,aGVybw==", embedded: true };

describe("portable brief", () => {
  it("uses embedded hero for both markup and card background when cats fail", () => {
    const html = renderToStaticMarkup(<App data={{ assets: embedded, catsError: "Коты недоступны" }} />);
    expect(html).toContain(embedded.heroImage);
    expect(html).toContain("Коты недоступны");
    expect(html).not.toMatch(/frontend\/public|\.\.\/public|\/hero-bg\.jpg/);
    expect(html).not.toContain("+10 к настроению");
    expect(html).toContain('href="#cats-details"');
    expect(html).toContain('id="cats-details"');
  });

  it("does not request a missing hero in an embedded report", () => {
    const html = renderToStaticMarkup(<App data={{ assets: { embedded: true } }} />);
    expect(html).not.toContain("<img");
    expect(html).not.toContain("hero-bg.jpg");
  });

  it("distinguishes unreadable tasks from an empty list", () => {
    const html = renderToStaticMarkup(<App data={{ tasksError: "Не удалось прочитать tasks.md" }} />);
    expect(html).toContain("Не удалось прочитать tasks.md");
    expect(html).toContain("задачи недоступны");
    expect(html).not.toContain("Свободный день");
  });

  it("does not present a holiday API failure as a real holiday or no holidays", () => {
    const html = renderToStaticMarkup(<App data={{ holidays: { error: true, items: ["не удалось получить данные"] } }} />);
    expect(html).toContain("Данные о праздниках временно недоступны");
    expect(html).not.toContain("Официальные праздники:");
    expect(html).not.toContain("Официальных праздников сегодня нет");
  });

  it("renders every downloaded cat and escapes task markup", () => {
    const cats = [1, 2, 3].map((id) => ({ src: `data:image/png;base64,${id}`, alt: `Кот ${id}` }));
    const html = renderToStaticMarkup(<App data={{ cats, assets: embedded, tasks: ["<script>alert(1)</script>"] }} />);
    for (const cat of cats) expect(html).toContain(`alt="${cat.alt}"`);
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });
});
