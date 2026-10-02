import { NextResponse } from 'next/server';
import { generateRoleCraftOutcome, generateRoleCraftStream } from '@/lib/rolecraft/prompt-nenujna-engine';
import { RoleCraftInput } from '@/lib/rolecraft/types';

export async function POST(req: Request) {
  try {
    let body: any;
    try {
      body = await req.json();
    } catch {
      return NextResponse.json(
        { error: 'Noto\'g\'ri so\'rov formati (JSON kutilgan edi)' },
        { status: 400 }
      );
    }

    const { roleTitle, companyContext, coreBusinessPain, techStackAndSkills } = body || {};

    // 1. Validation according to spec & interfaces
    if (typeof roleTitle !== 'string' || roleTitle.trim().length < 3) {
      return NextResponse.json(
        { error: 'Lavozim nomi (roleTitle) kamida 3 ta belgidan iborat bo\'lishi kerak' },
        { status: 400 }
      );
    }

    if (typeof companyContext !== 'string' || companyContext.trim().length < 10) {
      return NextResponse.json(
        { error: 'Kompaniya konteksti (companyContext) kamida 10 ta belgidan iborat bo\'lishi kerak' },
        { status: 400 }
      );
    }

    if (typeof coreBusinessPain !== 'string' || coreBusinessPain.trim().length < 10) {
      return NextResponse.json(
        { error: 'Asosiy biznes dardi (coreBusinessPain) kamida 10 ta belgidan iborat bo\'lishi kerak' },
        { status: 400 }
      );
    }

    if (typeof techStackAndSkills !== 'string' || techStackAndSkills.trim().length < 3) {
      return NextResponse.json(
        { error: 'Texnologik stak (techStackAndSkills) kamida 3 ta belgidan iborat bo\'lishi kerak' },
        { status: 400 }
      );
    }

    const input: RoleCraftInput = {
      roleTitle: roleTitle.trim(),
      companyContext: companyContext.trim(),
      coreBusinessPain: coreBusinessPain.trim(),
      techStackAndSkills: techStackAndSkills.trim(),
    };

    // 2. Check if SSE streaming is requested
    const acceptsSse = req.headers.get('accept')?.includes('text/event-stream');
    const isStreamRequested = acceptsSse || body.stream === true;

    if (isStreamRequested) {
      const encoder = new TextEncoder();
      const customStream = new ReadableStream({
        async start(controller) {
          try {
            for await (const chunk of generateRoleCraftStream(input)) {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
            }
            controller.enqueue(encoder.encode('data: [DONE]\n\n'));
            controller.close();
          } catch (err) {
            controller.error(err);
          }
        },
      });

      return new Response(customStream, {
        headers: {
          'Content-Type': 'text/event-stream; charset=utf-8',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
        },
      });
    }

    // 3. Standard JSON response
    const output = await generateRoleCraftOutcome(input);
    return NextResponse.json({ success: true, data: output }, { status: 200 });
  } catch (error) {
    console.error('RoleCraft generation error:', error instanceof Error ? error.message : 'Unknown error');
    return NextResponse.json(
      { error: 'Generatsiya jarayonida kutilmagan xatolik yuz berdi' },
      { status: 500 }
    );
  }
}
