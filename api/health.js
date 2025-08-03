// Vercel serverless function for health check
export default function handler(req, res) {
  if (req.method === "GET") {
    res.status(200).json({
      status: "healthy",
      timestamp: new Date().toISOString(),
      environment: "vercel",
      version: "1.0.0",
    })
  } else {
    res.setHeader("Allow", ["GET"])
    res.status(405).end(`Method ${req.method} Not Allowed`)
  }
}
