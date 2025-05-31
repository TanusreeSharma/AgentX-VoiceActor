import type {ApiConfig, AnalysisType, ContractData} from './types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8501'

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

        try {
            const response = await fetch(`${API_BASE_URL}/api/analyze`, {
                method: 'POST',
                body: formData,
            })

            const responseText = await response.text()

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

            // Return the simplified structure
            return {
                analysis: data.analysis || '',
                keyPoints: data.key_points || '',
                negotiations: data.negotiations || ''
            }
        } catch (error) {
            console.error("API call error:", error)
            throw error
        }
    }
}

export const apiService = new ApiService()