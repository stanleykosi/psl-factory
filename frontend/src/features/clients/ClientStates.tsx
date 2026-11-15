// 403 and 404 look the same (INV-ACCESS): nothing about the client is shown, not even its id or the server's message.
import Link from 'next/link';

export function ClientNoAccess({ list = false }: { list?: boolean }) {
  return (
    <section className="psl-panel clients__noaccess" aria-labelledby="clients-noaccess-title">
      <div className="psl-panel__body">
        <span className="psl-tag psl-tag--neutral clients__noaccesstag">NO ACCESS</span>
        <h1 id="clients-noaccess-title" className="shell-title">
          {list ? 'You can’t open the clients' : 'You can’t open this client'}
        </h1>
        <p className="clients__plain">
          {list ? 'Your access does not cover any client.' : 'It belongs to work you don’t have access to.'} Nothing about it is shown here.
        </p>
        <p className="clients__plain">
          <Link className="psl-btn psl-btn--dark psl-btn--lg" href="/projects">
            Back to projects
          </Link>
        </p>
      </div>
    </section>
  );
}
