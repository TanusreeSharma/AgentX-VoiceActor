import type {ApiConfig, AnalysisType, ContractData} from './types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export class ApiService {
    private config: ApiConfig | null = null

    setConfig(config: ApiConfig) {
        this.config = config
    }

    async uploadAndAnalyze(file: File, analysisType: AnalysisType): Promise<ContractData> {
        if (!this.config?.openaiApiKey) {
            throw new Error('OpenAI API key not configured')
        }

        const formData = new FormData()
        formData.append('file', file)
        formData.append('openai_api_key', this.config.openaiApiKey)
        formData.append('analysis_type', analysisType.type)

        if (analysisType.customQuery) {
            formData.append('custom_query', analysisType.customQuery)
        }

        // Log the request details
        console.log("Sending analysis request:", {
            file: file.name,
            fileSize: file.size,
            analysisType: analysisType.type,
            hasCustomQuery: !!analysisType.customQuery,
            apiUrl: `${API_BASE_URL}/api/analyze`
        });

        try {
            const response = await fetch(`${API_BASE_URL}/api/analyze`, {
                method: 'POST',
                body: formData,
            })

            const responseText = await response.text()
            console.log("Response status:", response.status)
            console.log("Response text:", responseText)

            if (!response.ok) {
                // Try to parse error details
                let errorDetail = 'Analysis failed'
                try {
                    const errorData = JSON.parse(responseText)
                    errorDetail = errorData.detail || errorDetail
                } catch {
                    errorDetail = responseText || errorDetail
                }
                throw new Error(errorDetail)
            }

            // Parse successful response
            const data = JSON.parse(responseText)
            console.log("Parsed response data:", data)

            // Return the simplified structure
            return {
                analysis: data.analysis,
                keyPoints: data.key_points,
                recommendations: data.recommendations,
                riskScore: data.risk_score
            }
        } catch (error) {
            console.error("API call error:", error)
            throw error
        }
    }
}

export const apiService = new ApiService()