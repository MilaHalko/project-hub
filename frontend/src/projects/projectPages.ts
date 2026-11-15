import type { InfiniteData } from "@tanstack/react-query";
import type { Project } from "../api/projects";

export const PAGE_SIZE = 20;

export function visibleRows(pages: Project[][]): Project[] {
  return pages.flatMap((page, index) =>
    index < pages.length - 1 ? page.slice(0, -1) : page.slice(0, PAGE_SIZE),
  );
}

export function withoutProject(
  data: InfiniteData<Project[]>,
  id: string,
): InfiniteData<Project[]> {
  return {
    ...data,
    pages: data.pages.map((page) => [
      ...page.slice(0, PAGE_SIZE).filter((item) => item.id !== id),
      ...page.slice(PAGE_SIZE),
    ]),
  };
}
