"use strict";

const query = document.querySelector("#q");
const domain = document.querySelector("#domain");
const dateInput = document.querySelector("#publication-date");
const allDates = document.querySelector("#all-dates");
const showMore = document.querySelector("#show-more");
const calendarDays = document.querySelector("#calendar-days");
const papers = Array.from(document.querySelectorAll(".paper"));
const formatNumber = new Intl.NumberFormat("en-US");
const formatDate = new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
const formatMonth = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
const initialDate = document.body.dataset.calendarDate;
let month = new Date(`${initialDate.slice(0, 7)}-01T00:00:00Z`);
let selectedDate = "";
let visibleLimit = 50;

function renderCalendar(matches) {
  const counts = new Map();
  for (const paper of matches) {
    const day = paper.dataset.published;
    if (day) counts.set(day, (counts.get(day) || 0) + 1);
  }
  document.querySelector("#calendar-month").textContent = formatMonth.format(month);
  const cells = document.createDocumentFragment();
  for (let blank = 0; blank < month.getUTCDay(); blank++) {
    const space = document.createElement("span");
    space.setAttribute("aria-hidden", "true");
    cells.append(space);
  }
  const daysInMonth = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth() + 1, 0)).getUTCDate();
  for (let day = 1; day <= daysInMonth; day++) {
    const date = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth(), day));
    const key = date.toISOString().slice(0, 10);
    const count = counts.get(key) || 0;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `calendar-day${count ? " has-papers" : ""}`;
    button.dataset.date = key;
    button.setAttribute("aria-pressed", String(key === selectedDate));
    button.setAttribute("aria-label", `${formatDate.format(date)}: ${formatNumber.format(count)} ${count === 1 ? "paper" : "papers"}`);
    const dayLabel = document.createElement("span");
    dayLabel.textContent = day;
    button.append(dayLabel);
    if (count) {
      const badge = document.createElement("span");
      badge.className = "day-count";
      badge.textContent = formatNumber.format(count);
      button.append(badge);
    }
    cells.append(button);
  }
  calendarDays.replaceChildren(cells);
}

function render() {
  const search = query.value.trim().toLowerCase();
  const matches = papers.filter(paper => paper.dataset.search.includes(search) && (!domain.value || paper.dataset.domain === domain.value));
  const results = matches.filter(paper => !selectedDate || paper.dataset.published === selectedDate);
  const visible = results.slice(0, visibleLimit);
  for (const paper of papers) paper.hidden = true;
  for (const paper of visible) paper.hidden = false;
  document.querySelector("#results-heading").textContent = selectedDate
    ? `Published on ${formatDate.format(new Date(`${selectedDate}T00:00:00Z`))}`
    : "All publication dates";
  document.querySelector("#result-count").textContent = `Showing ${formatNumber.format(visible.length)} of ${formatNumber.format(results.length)} ${results.length === 1 ? "paper" : "papers"}`;
  document.querySelector("#empty-results").hidden = results.length !== 0;
  showMore.hidden = results.length <= visibleLimit;
  allDates.setAttribute("aria-pressed", String(!selectedDate));
  dateInput.value = selectedDate;
  renderCalendar(matches);
}

function selectDate(date) {
  selectedDate = date;
  visibleLimit = 50;
  if (date) month = new Date(`${date.slice(0, 7)}-01T00:00:00Z`);
  render();
}

calendarDays.addEventListener("click", event => {
  const button = event.target.closest("button[data-date]");
  if (button) {
    selectDate(button.dataset.date);
    calendarDays.querySelector(`[data-date="${selectedDate}"]`).focus();
  }
});
dateInput.addEventListener("change", () => selectDate(dateInput.value));
allDates.addEventListener("click", () => selectDate(""));
for (const [id, offset] of [["previous-month", -1], ["next-month", 1]]) {
  document.querySelector(`#${id}`).addEventListener("click", () => {
    month = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth() + offset, 1));
    render();
  });
}
for (const input of [query, domain]) {
  input.addEventListener(input === query ? "input" : "change", () => {
    visibleLimit = 50;
    render();
  });
}
showMore.addEventListener("click", () => {
  visibleLimit += 50;
  render();
});
render();
