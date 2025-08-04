import { 
  Configuration, 
  GetJournalistByIdRequest, 
  SearchArticlesRequest, 
  SearchCompaniesRequest, 
  SearchJournalistsRequest, 
  SearchPeopleRequest, 
  SearchSourcesRequest, 
  SearchStoriesRequest, 
  SearchSummarizerRequest, 
  SearchTopicsRequest, 
  SearchWikipediaRequest, 
  V1Api, 
  VectorSearchArticlesRequest, 
  VectorSearchWikipediaRequest 
} from '@goperigon/perigon-ts';

export class PerigonService {
  private client: V1Api;

  constructor(apiKey?: string) {
    this.client = new V1Api(
      new Configuration({
        apiKey: (apiKey ?? process.env.PERIGON_API_KEY) as string,
      })
    );
  }

  // News & Articles Endpoints
  async searchArticles(requestParameters: Partial<SearchArticlesRequest> = {}) {
    return await this.client.searchArticles(requestParameters);
  }

  async vectorSearchArticles(requestParameters: VectorSearchArticlesRequest) {
    return await this.client.vectorSearchArticles(requestParameters);
  }

  // Entities Endpoints
  async searchCompanies(requestParameters: Partial<SearchCompaniesRequest> = {}) {
    return await this.client.searchCompanies(requestParameters);
  }

  async searchPeople(requestParameters: Partial<SearchPeopleRequest> = {}) {
    return await this.client.searchPeople(requestParameters);
  }

  async searchJournalists(requestParameters: Partial<SearchJournalistsRequest> = {}) {
    return await this.client.searchJournalists(requestParameters);
  }

  async getJournalistById(requestParameters: GetJournalistByIdRequest) {
    return await this.client.getJournalistById(requestParameters);
  }

  // Content Discovery Endpoints
  async searchStories(requestParameters: Partial<SearchStoriesRequest> = {}) {
    return await this.client.searchStories(requestParameters);
  }

  async searchTopics(requestParameters: Partial<SearchTopicsRequest>) {
    return await this.client.searchTopics(requestParameters);
  }

  async searchSources(requestParameters: Partial<SearchSourcesRequest> = {}) {
    return await this.client.searchSources(requestParameters);
  }

  // AI Features
  async searchSummarizer(requestParameters: SearchSummarizerRequest) {
    return await this.client.searchSummarizer(requestParameters);
  }

  // Knowledge Base Endpoints
  async searchWikipedia(requestParameters: Partial<SearchWikipediaRequest> = {}) {
    return await this.client.searchWikipedia(requestParameters);
  }

  async vectorSearchWikipedia(requestParameters: VectorSearchWikipediaRequest) {
    return await this.client.vectorSearchWikipedia(requestParameters);
  }
}

// Export default instance
export const perigonService = new PerigonService();
