'use client';

import { useState } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { useAppStore } from '@/store/appStore';
import { useCreateIncident, useRemoveIncident } from '@/hooks/useApi';
import { INCIDENT_ICONS, cn } from '@/lib/utils';
import { AlertCircle, Plus, Trash2, Loader2 } from 'lucide-react';
import type { IncidentType, IncidentSeverity, Incident } from '@/types';

const INCIDENT_TYPES: IncidentType[] = ['accident', 'flood', 'crime', 'road_closure', 'construction', 'event'];
const SEVERITIES: IncidentSeverity[] = ['low', 'medium', 'high', 'critical'];

const severityColors: Record<IncidentSeverity, string> = {
  low: 'safe',
  medium: 'moderate',
  high: 'caution',
  critical: 'unsafe',
};

export default function IncidentCenterPage() {
  const { activeIncidents, addIncident, removeIncident } = useAppStore();
  const createMutation = useCreateIncident();
  const removeMutation = useRemoveIncident();

  const [edgeId, setEdgeId] = useState('');
  const [incidentType, setIncidentType] = useState<IncidentType>('accident');
  const [severity, setSeverity] = useState<IncidentSeverity>('medium');
  const [description, setDescription] = useState('');

  const handleAdd = () => {
    if (!edgeId || !description) return;
    createMutation.mutate(
      { edge_id: edgeId, incident_type: incidentType, severity, description },
      {
        onSuccess: (data) => {
          addIncident(data);
          setEdgeId('');
          setDescription('');
        },
        onError: () => {
          // Fallback: add a local incident if backend unavailable
          const localIncident: Incident = {
            id: `local-${Date.now()}`,
            edge_id: edgeId,
            incident_type: incidentType,
            severity,
            description,
            created_at: new Date().toISOString(),
            status: 'active',
          };
          addIncident(localIncident);
          setEdgeId('');
          setDescription('');
        },
      }
    );
  };

  const handleRemove = (incident: Incident) => {
    removeMutation.mutate(
      { incident_id: incident.id },
      {
        onSuccess: () => removeIncident(incident.id),
        onError: () => removeIncident(incident.id), // optimistic removal
      }
    );
  };

  const statusCounts = activeIncidents.reduce(
    (acc, inc) => {
      acc[inc.severity] = (acc[inc.severity] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-warning/10 border border-warning/20 flex items-center justify-center">
            <AlertCircle size={20} className="text-warning" />
          </div>
          <div>
            <h1 className="font-display font-bold text-2xl text-white">Incident Center</h1>
            <p className="text-slate-400 text-sm">
              Create and manage incidents that update the temporal risk graph in real-time
            </p>
          </div>
        </div>

        {/* Status cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {SEVERITIES.map((sev) => (
            <Card key={sev} className="p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400 capitalize">{sev}</span>
                <Badge variant={severityColors[sev] as any}>{sev}</Badge>
              </div>
              <div className="font-display font-bold text-2xl text-white">{statusCounts[sev] || 0}</div>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-6">
          {/* Create form */}
          <Card>
            <CardHeader>
              <CardTitle>Create Incident</CardTitle>
              <CardDescription>Report a new incident affecting the road network</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Edge ID</Label>
                <Input
                  placeholder="e.g. edge_4521"
                  value={edgeId}
                  onChange={(e) => setEdgeId(e.target.value)}
                />
              </div>

              <div>
                <Label>Incident Type</Label>
                <Select value={incidentType} onValueChange={(v: any) => setIncidentType(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {INCIDENT_TYPES.map((type) => (
                      <SelectItem key={type} value={type}>
                        {INCIDENT_ICONS[type]} {type.replace('_', ' ')}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Severity</Label>
                <Select value={severity} onValueChange={(v: any) => setSeverity(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SEVERITIES.map((sev) => (
                      <SelectItem key={sev} value={sev} className="capitalize">
                        {sev}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Description</Label>
                <Input
                  placeholder="Describe the incident"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              <Button
                onClick={handleAdd}
                disabled={!edgeId || !description || createMutation.isPending}
                className="w-full"
                size="lg"
              >
                {createMutation.isPending ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus size={16} />
                    Add Incident
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Incident table */}
          <Card>
            <CardHeader>
              <CardTitle>Active Incidents</CardTitle>
              <CardDescription>{activeIncidents.length} incidents currently affecting the risk graph</CardDescription>
            </CardHeader>
            <CardContent>
              {activeIncidents.length === 0 ? (
                <div className="text-center py-12">
                  <AlertCircle size={32} className="text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-400 text-sm">No active incidents reported.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-slate-500 border-b border-border">
                        <th className="py-2 pr-4">Type</th>
                        <th className="py-2 pr-4">Edge ID</th>
                        <th className="py-2 pr-4">Severity</th>
                        <th className="py-2 pr-4">Description</th>
                        <th className="py-2 pr-4">Status</th>
                        <th className="py-2"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeIncidents.map((incident) => (
                        <tr key={incident.id} className="border-b border-border/50 hover:bg-white/[0.02]">
                          <td className="py-3 pr-4">
                            <span className="flex items-center gap-2 text-slate-200">
                              <span>{INCIDENT_ICONS[incident.incident_type]}</span>
                              <span className="capitalize">{incident.incident_type.replace('_', ' ')}</span>
                            </span>
                          </td>
                          <td className="py-3 pr-4 text-slate-400 font-mono text-xs">{incident.edge_id}</td>
                          <td className="py-3 pr-4">
                            <Badge variant={severityColors[incident.severity] as any} className="capitalize">
                              {incident.severity}
                            </Badge>
                          </td>
                          <td className="py-3 pr-4 text-slate-400 max-w-[200px] truncate">{incident.description}</td>
                          <td className="py-3 pr-4">
                            <Badge variant="outline" className="capitalize">
                              {incident.status}
                            </Badge>
                          </td>
                          <td className="py-3">
                            <button
                              onClick={() => handleRemove(incident)}
                              className="p-1.5 rounded-lg hover:bg-danger/10 text-slate-500 hover:text-danger transition-colors"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
