import { source } from '@/lib/source';
import {
  DocsBody,
  DocsDescription,
  DocsPage,
  DocsTitle,
  PageLastUpdate,
} from 'fumadocs-ui/layouts/docs/page';
import { notFound } from 'next/navigation';
import { getMDXComponents } from '@/mdx-components';
import type { Metadata } from 'next';
import { createRelativeLink } from 'fumadocs-ui/mdx';

type PageParams = {
  slug?: string[];
};

export default async function Page({
  params,
}: {
  params: Promise<PageParams>;
}) {
  const resolved = await params;
  const page = source.getPage(resolved.slug);
  if (!page) notFound();
  const isHome = !resolved.slug || resolved.slug.length === 0;

  const MDX = page.data.body;
  const lastModified = page.data.lastModified;

  return (
    <DocsPage toc={page.data.toc} full={page.data.full}>
      {!isHome && <DocsTitle>{page.data.title}</DocsTitle>}
      {!isHome && <DocsDescription>{page.data.description}</DocsDescription>}
      <DocsBody>
        <MDX
          components={getMDXComponents({
            a: createRelativeLink(source, page),
          })}
        />
      </DocsBody>
      {lastModified && <PageLastUpdate date={lastModified} />}
    </DocsPage>
  );
}

export async function generateStaticParams() {
  return source.generateParams();
}

export async function generateMetadata({
  params,
}: {
  params: Promise<PageParams>;
}): Promise<Metadata> {
  const resolved = await params;
  const page = source.getPage(resolved.slug);
  if (!page) notFound();

  return {
    title: page.data.title,
    description: page.data.description,
  };
}
