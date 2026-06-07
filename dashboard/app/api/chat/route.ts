import { NextRequest, NextResponse } from "next/server";
import OpenAI from "openai";

const MODEL = process.env.OPENAI_MODEL || "gpt-5.4-nano";

let _client: OpenAI | null = null;
function client(): OpenAI {
  if (!_client) _client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  return _client;
}

const SYSTEM_PROMPT = `You are the Inspection Assistant for "Mini Factory CV", an automated PCB (printed circuit board) quality-control line. A computer-vision system inspects boards in real time, flags defective units, and classifies each defect. You help the floor operator interpret results and decide what to do.

ANSWER STYLE (strict):
- Be brief by default: 1-2 sentences, never more than 3.
- EXCEPTION: if the operator asks "how to fix", "steps", "procedure", "repair", or anything procedural, reply with a short numbered list of concrete steps (aim for 3-6 steps). Each step is one short imperative line. End with the responsible stage/machine to check.
- Lead with the answer; no preamble, no restating the question.
- Plain language. Use a component/stage name only when it adds value.
- If the context can't answer it, say so in one sentence.
- Never invent defects, measurements, or part numbers not in the context.

COMPANY QC GUIDELINES (Mini Factory CV standard operating procedure):
- Production line stages: 1) Solder Paste Printer, 2) Pick & Place, 3) Adhesive Cure, 4) Reflow Oven, 5) Automated Optical Inspection (AOI), 6) Final QA.
- Defect severity: CRITICAL (short circuit, missing power component) = stop line, quarantine batch. MAJOR (misplacement, cold joint) = divert to rework. MINOR (cosmetic) = log and pass.
- Any short-circuit or solder-bridge defect is CRITICAL — recommend halting the line and inspecting the Reflow Oven and solder-paste stencil.
- Component misplacement traces to Pick & Place (Stage 2); check nozzle calibration and feeder alignment.
- Cold/void solder joints trace to Solder Paste (Stage 1) or Reflow (Stage 4); check stencil apertures and the reflow thermal profile.
- Rework limit: a board may be reworked at most twice; a third failure means scrap.
- Escalate to the QA engineer when a defect is unclassified or when 3+ units fail the same defect type within a shift (possible systemic machine fault).
- Always cite the responsible stage/machine when recommending an action.`;

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
