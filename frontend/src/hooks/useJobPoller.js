import { useState, useEffect, useRef } from 'react'
import { getJobStatus } from '../api/client'

export function useJobPoller(jobId) {
  const [job, setJob] = useState(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!jobId) return
    const poll = async () => {
      try {
        const data = await getJobStatus(jobId)
        setJob(data)
        if (data.status === 'done' || data.status === 'error') {
          clearInterval(intervalRef.current)
        }
      } catch {
        // ignora erros transitórios de rede
      }
    }
    poll()
    intervalRef.current = setInterval(poll, 2000)
    return () => clearInterval(intervalRef.current)
  }, [jobId])

  return job
}
