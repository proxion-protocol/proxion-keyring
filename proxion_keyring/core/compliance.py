import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

class ComplianceReporter:
    """V7.10: Generate monthly security compliance reports."""
    
    def __init__(self, pod_local_root: str):
        self.pod_local_root = pod_local_root
        self.reports_dir = os.path.join(pod_local_root, "compliance_reports")
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_monthly_report(self, stats: Dict[str, Any]) -> str:
        """Generate PDF compliance report for the current month."""
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        report_path = os.path.join(self.reports_dir, f"compliance_report_{period}.pdf")
        
        # Extract data
        metrics = stats.get("metrics", {})
        security_council = stats.get("security_council", {})
        
        # Calculate summary stats
        total_forges = len(metrics.get("forge_history", []))
        successful_forges = sum(1 for f in metrics.get("forge_history", []) if f.get("success"))
        total_cves_fixed = sum(
            f.get("pre_vulns", 0) - f.get("post_vulns", 0)
            for f in metrics.get("forge_history", [])
            if f.get("success")
        )
        
        # Create PDF
        doc = SimpleDocTemplate(report_path, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title = Paragraph(f"<b>Proxion Security Compliance Report</b><br/>{period}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.5*inch))
        
        # Executive Summary
        story.append(Paragraph("<b>Executive Summary</b>", styles['Heading2']))
        summary_data = [
            ["Metric", "Value"],
            ["Total Forges", str(total_forges)],
            ["Successful Forges", str(successful_forges)],
            ["Success Rate", f"{metrics.get('success_rate_30d', 0)*100:.1f}%"],
            ["Total CVEs Fixed", str(total_cves_fixed)],
            ["Fleet Health Score", f"{stats.get('fleet_health', 0)}%"],
            ["MTTR (Critical)", self._format_mttr(metrics.get("mttr_critical", 0))],
            ["MTTR (High)", self._format_mttr(metrics.get("mttr_high", 0))]
        ]
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Current Vulnerabilities
        story.append(Paragraph("<b>Current Vulnerability Status</b>", styles['Heading2']))
        vuln_data = [
            ["Severity", "Count"],
            ["Critical", str(security_council.get("total_critical", 0))],
            ["High", str(security_council.get("total_high", 0))],
            ["Medium", str(security_council.get("total_medium", 0))]
        ]
        
        vuln_table = Table(vuln_data)
        vuln_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(vuln_table)
        
        # Build PDF
        doc.build(story)
        
        return report_path
    
    def _format_mttr(self, seconds: int) -> str:
        """Format MTTR in human-readable form."""
        if seconds < 3600:
            return f"{seconds // 60}m"
        if seconds < 86400:
            return f"{seconds // 3600}h"
        return f"{seconds // 86400}d"
    
    def generate_json_report(self, stats: Dict[str, Any]) -> str:
        """Generate JSON compliance report."""
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        report_path = os.path.join(self.reports_dir, f"compliance_report_{period}.json")
        
        report = {
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_forges": len(stats.get("metrics", {}).get("forge_history", [])),
                "success_rate": stats.get("metrics", {}).get("success_rate_30d", 0),
                "fleet_health": stats.get("fleet_health", 0)
            },
            "vulnerabilities": {
                "critical": stats.get("security_council", {}).get("total_critical", 0),
                "high": stats.get("security_council", {}).get("total_high", 0),
                "medium": stats.get("security_council", {}).get("total_medium", 0)
            },
            "forge_history": stats.get("metrics", {}).get("forge_history", [])
        }
        
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return report_path
