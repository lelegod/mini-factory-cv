import { NextRequest, NextResponse } from "next/server";
import OpenAI from "openai";

const MODEL = process.env.OPENAI_MODEL || "gpt-5.4-nano";

let _client: OpenAI | null = null;
function client(): OpenAI {
  if (!_client) _client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  return _client;
}

const SYSTEM_PROMPT = `You are the Inspection Assistant for an automated PCB (printed circuit board) quality-control line called "Mini Factory CV".

A computer-vision system inspects boards as they move through the line, flags defective units, and classifies each defect. You help the operator understand the current inspection results and decide what to do next.

Guidelines:
- Be concise, precise, and professional — you are speaking to a manufacturing engineer on the floor.
- Ground every answer in the CURRENT INSPECTION CONTEXT provided below. Do not invent defects that are not listed.
- When asked about a defect, reference its tag ID, defect type, the likely root cause, the recommended corrective action, and which machine/stage to inspect.
- If the operator asks something the context cannot answer, say so plainly and suggest what data would be needed.
- Keep responses short (1-4 sentences) unless the operator explicitly asks for detail.
- Never fabricate measurements, part numbers, or readings that are not in the context.`;

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

export async function POST(req: NextRequest) {
  if (!process.env.OPENAI_API_KEY) {
    return NextResponse.json({ error: "OPENAI_API_KEY not set" }, { status: 500 });
  }

  const { messages, context } = (await req.json()) as {
    messages: ChatMessage[];
    context?: string;
  };

  const contextBlock = context && context.trim().length > 0
    ? context
    : "No defective units are currently flagged. The line is clear.";

  try {
    const completion = await client().chat.completions.create({
      model: MODEL,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "system", content: `CURRENT INSPECTION CONTEXT:\n${contextBlock}` },
        ...messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.text,
        })),
      ],
    });

    const reply = completion.choices[0]?.message?.content?.trim() ?? "(no response)";
    return NextResponse.json({ reply });
  } catch (e) {
    console.error("Chat error:", e);
    return NextResponse.json({ error: "Assistant unavailable" }, { status: 500 });
  }
}
