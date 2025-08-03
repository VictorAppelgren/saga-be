export interface BaseEntity {
  id: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
}

export interface PaginationOptions {
  page: number;
  limit: number;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

export class Logger {
  static info(message: string, meta?: Record<string, any>): void {
    console.log(`[INFO] ${new Date().toISOString()}: ${message}`, meta || '');
  }

  static error(message: string, error?: Error): void {
    console.error(`[ERROR] ${new Date().toISOString()}: ${message}`, error || '');
  }

  static warn(message: string, meta?: Record<string, any>): void {
    console.warn(`[WARN] ${new Date().toISOString()}: ${message}`, meta || '');
  }
}

export const createApiResponse = <T>(
  success: boolean,
  data?: T,
  error?: string
): ApiResponse<T> => ({
  success,
  data,
  error,
  timestamp: new Date().toISOString()
});

export const validateEnv = (requiredVars: string[]): void => {
  const missing = requiredVars.filter(varName => !process.env[varName]);
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }
};