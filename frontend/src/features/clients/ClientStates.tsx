// 403 and 404 look the same (INV-ACCESS): nothing about the client is shown, not even its id or the server's message.
import { buttonClass, PageTitle, Tag } from '@/components';
import Link from 'next/link';

export function ClientNoAccess({ list = false }: { list?: boolean }) {
  return (
    <section className="psl-panel clients__noaccess" aria-label="No access">
      <div className="psl-panel__body">
        <Tag tone="neutral" className="clients__noaccesstag">
          NO ACCESS
        </Tag>
        <PageTitle>{list ? 'You can’t open the clients' : 'You can’t open this client'}</PageTitle>
        <p className="clients__plain">
          {list ? 'Your access does not cover any client.' : 'It belongs to work you don’t have access to.'} Nothing about it is shown here.
        </p>
        <p className="clients__plain">
          <Link className={buttonClass('dark', 'lg')} href="/projects">
            Back to projects
          </Link>
        </p>
      </div>
    </section>
  );
}
