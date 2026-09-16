// Wraps the compiled Express app as a Netlify Function so /api/* routes
// work without running a persistent Node server.
import serverless from "serverless-http";
import app from "../../dist/server";

export const handler = serverless(app);
