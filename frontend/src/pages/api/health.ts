import type { APIRoute } from 'astro';
import { getReport } from '../../data/report';

export const GET: APIRoute = async () => {
  const timestamp = new Date().toISOString();

  try {
    const report = await getReport();

    const dataCheck = {
      status: 'ok' as const,
      lastUpdated: report.generatedAt,
      stockCount: report.allStocks?.length ?? 0,
      picksCount: (report.picks?.short?.length ?? 0) + (report.picks?.medium?.length ?? 0) + (report.picks?.long?.length ?? 0),
    };

    const response = {
      status: 'ok' as const,
      timestamp,
      checks: {
        data: dataCheck,
      },
    };

    return new Response(JSON.stringify(response, null, 2), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    const response = {
      status: 'error' as const,
      timestamp,
      checks: {
        data: {
          status: 'error' as const,
          message: error instanceof Error ? error.message : 'Unknown error',
        },
      },
    };

    return new Response(JSON.stringify(response, null, 2), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};
