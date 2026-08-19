import { dayToDate, dateToDay, dayLabel, getShootDateRange, formatDateDisplay } from "./days";

describe("days.js utility", () => {
  const prod = {
    production_id: "prod_001",
    title: "The Long Dark Take",
    start_date: "2026-08-19",
    total_shoot_days: 3,
  };

  const longProd = {
    production_id: "prod_002",
    title: "IRON HORIZON",
    start_date: "2026-08-19",
    total_shoot_days: 160,
  };

  const legacyProd = {
    production_id: "prod_old",
    title: "Legacy Shoot",
    total_shoot_days: 5,
  };

  test("dayToDate: converts 1-based shooting day to ISO date correctly", () => {
    expect(dayToDate(prod, 1)).toBe("2026-08-19");
    expect(dayToDate(prod, 2)).toBe("2026-08-20");
    expect(dayToDate(prod, 3)).toBe("2026-08-21");
    // Long production Day 160
    expect(dayToDate(longProd, 160)).toBe("2027-01-25");
  });

  test("dateToDay: converts ISO date back to 1-based shooting day", () => {
    expect(dateToDay(prod, "2026-08-19")).toBe(1);
    expect(dateToDay(prod, "2026-08-20")).toBe(2);
    expect(dateToDay(prod, "2026-08-21")).toBe(3);
    expect(dateToDay(longProd, "2027-01-25")).toBe(160);
  });

  test("dayLabel: formats label as 'Day N · Weekday, Month Day'", () => {
    expect(dayLabel(prod, 1)).toBe("Day 1 · Wed, Aug 19");
    expect(dayLabel(prod, 2)).toBe("Day 2 · Thu, Aug 20");
    expect(dayLabel(prod, 3)).toBe("Day 3 · Fri, Aug 21");
  });

  test("getShootDateRange: returns start and end ISO dates", () => {
    const range = getShootDateRange(prod);
    expect(range.start).toBe("2026-08-19");
    expect(range.end).toBe("2026-08-21");

    const longRange = getShootDateRange(longProd);
    expect(longRange.start).toBe("2026-08-19");
    expect(longRange.end).toBe("2027-01-25");
  });

  test("graceful fallbacks when production has no dates", () => {
    expect(dayToDate(legacyProd, 2)).toBeNull();
    expect(dateToDay(legacyProd, "2026-08-20")).toBeNull();
    expect(dayLabel(legacyProd, 2)).toBe("Day 2");
    expect(dayLabel(null, 4)).toBe("Day 4");
    expect(dayLabel(prod, null)).toBe("Day —");
  });
});
