// Helpers for the paginated envelope returned by list endpoints:
//   { items: [...], total, page, page_size, pages }
// They also accept a legacy bare array so old payloads keep working.

export const pageItems = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
};

export const pageMeta = (payload) => {
  if (Array.isArray(payload)) {
    return { total: payload.length, page: 1, pageSize: payload.length || 1, pages: 1 };
  }
  const total = Number(payload?.total ?? payload?.items?.length ?? 0);
  const page = Number(payload?.page ?? 1);
  const pageSize = Number(payload?.page_size ?? total ?? 1);
  const pages = Number(payload?.pages ?? (total ? 1 : 0));
  return { total, page, pageSize, pages };
};
