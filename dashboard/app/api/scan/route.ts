import { NextRequest, NextResponse } from "next/server";
import { setState } from "@/lib/state";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { approved_count, defective_count, approved_images, defective_images, camera_image_base64 } = body;

  setState({ approved_count, defective_count, approved_images, defective_images, camera_image_base64 });
  return NextResponse.json({ ok: true });
}
