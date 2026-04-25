import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { Topology, Agent } from '../types'

interface NetworkGraphProps {
  topology: Topology | null
  agents: Agent[]
}

const TYPE_COLORS: Record<string, string> = {
  company: '#667eea',
  competitor: '#f45c43',
  consumer: '#38ef7d',
  supplier: '#f7b731',
  government: '#5b2c6f',
  regulator: '#e74c3c',
  organization: '#3498db',
  individual: '#95a5a6',
}

const RELATION_COLORS: Record<string, string> = {
  competitor: '#f45c43',
  cooperative: '#38ef7d',
  supply: '#f7b731',
  demand: '#3498db',
  regulate: '#e74c3c',
  influence: '#9b59b6',
  neutral: '#bdc3c7',
}

export default function NetworkGraph({ topology, agents }: NetworkGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current || !topology || topology.nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const width = svgRef.current.clientWidth || 800
    const height = svgRef.current.clientHeight || 400

    // Create node map
    const nodeMap = new Map<string, any>()
    topology.nodes.forEach(node => {
      nodeMap.set(node.agent_id, {
        id: node.agent_id,
        label: node.label,
        type: node.type,
        x: width / 2 + (Math.random() - 0.5) * 200,
        y: height / 2 + (Math.random() - 0.5) * 200,
      })
    })

    // Create links
    const links = topology.edges.map(edge => {
      const sourceNode = topology.nodes.find(n => n.id === edge.source)
      const targetNode = topology.nodes.find(n => n.id === edge.target)
      return {
        source: sourceNode?.agent_id || '',
        target: targetNode?.agent_id || '',
        relation: edge.relation,
        weight: edge.weight,
      }
    }).filter(l => l.source && l.target)

    // Create force simulation
    const simulation = d3.forceSimulation(Array.from(nodeMap.values()))
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40))

    // Create container with zoom
    const container = svg.append('g')

    svg.call(d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        container.attr('transform', event.transform)
      }) as any)

    // Draw links
    const link = container.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', d => RELATION_COLORS[d.relation] || '#bdc3c7')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => Math.max(1, d.weight * 3))

    // Draw nodes
    const node = container.append('g')
      .selectAll('g')
      .data(Array.from(nodeMap.values()))
      .join('g')
      .attr('class', 'agent-node')
      .call(d3.drag<SVGGElement, any>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        }) as any)

    // Node circles
    node.append('circle')
      .attr('r', 24)
      .attr('fill', d => TYPE_COLORS[d.type] || '#95a5a6')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)

    // Node labels
    node.append('text')
      .text(d => d.label.substring(0, 8))
      .attr('text-anchor', 'middle')
      .attr('dy', 40)
      .attr('font-size', '11px')
      .attr('fill', '#333')

    // Node type icons (simplified as first char)
    node.append('text')
      .text(d => d.type.charAt(0).toUpperCase())
      .attr('text-anchor', 'middle')
      .attr('dy', 5)
      .attr('font-size', '14px')
      .attr('font-weight', 'bold')
      .attr('fill', '#fff')

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as any).x)
        .attr('y1', d => (d.source as any).y)
        .attr('x2', d => (d.target as any).x)
        .attr('y2', d => (d.target as any).y)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${width - 120}, 10)`)

    const legendTypes = Object.entries(TYPE_COLORS).slice(0, 5)
    legendTypes.forEach(([type, color], i) => {
      const g = legend.append('g').attr('transform', `translate(0, ${i * 20})`)
      g.append('circle').attr('r', 6).attr('fill', color)
      g.append('text')
        .text(type)
        .attr('x', 12)
        .attr('y', 4)
        .attr('font-size', '10px')
        .attr('fill', '#666')
    })

    return () => {
      simulation.stop()
    }
  }, [topology, agents])

  if (!topology || topology.nodes.length === 0) {
    return (
      <div className="network-container" style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#999'
      }}>
        暂无网络数据
      </div>
    )
  }

  return (
    <div className="network-container">
      <svg ref={svgRef} width="100%" height="100%" />
    </div>
  )
}
