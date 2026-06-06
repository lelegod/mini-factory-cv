import { NextRequest, NextResponse } from "next/server";
import { addScan } from "@/lib/state";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { status, tag_id, image_base64, camera_image_base64 } = body;

  if (!status || !["approved", "defective"].includes(status)) {
    return NextResponse.json({ error: "Invalid status" }, { status: 400 });
  }

  addScan({ status, tag_id, image_base64, camera_image_base64 });
  return NextResponse.json({ ok: true });
}
