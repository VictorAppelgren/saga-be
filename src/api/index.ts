import fastify from 'fastify';

const server = fastify({ logger: true });

const start = async () => {
  try {
    server.get('/health', async (request, reply) => {
      return { status: 'ok', timestamp: new Date().toISOString() };
    });

    const PORT = process.env.PORT || 3000;
    await server.listen({ port: Number(PORT), host: '0.0.0.0' });
    console.log(`API server running on port ${PORT}`);
  } catch (err) {
    server.log.error(err);
    process.exit(1);
  }
};

start();

export default server;