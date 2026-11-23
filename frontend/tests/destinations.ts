// /me destinations in the live shape (F-57): {key, title, django_url} objects. django_url is never used by the frame.
const TITLES: Record<string, string> = { my_work: 'My work', projects: 'Projects', overview: 'Overview', setup: 'Setup', clients: 'Clients', assistant: 'Assistant' };

export const destinationList = (keys: string[]) => keys.map((key) => ({ key, title: TITLES[key], django_url: '/retired/', url: `/${key}`, available: true }));
