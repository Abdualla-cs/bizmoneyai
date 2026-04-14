import { NextResponse, type NextRequest } from "next/server";

// The app uses backend JWT cookies for auth, so frontend middleware should stay neutral.
export function middleware(request: NextRequest) {
  void request;
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
