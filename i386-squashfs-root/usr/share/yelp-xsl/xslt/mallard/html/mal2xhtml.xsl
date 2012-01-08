<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<!--
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
details.

You should have received a copy of the GNU Lesser General Public License
along with this program; see the file COPYING.LGPL.  If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
02111-1307, USA.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:mal="http://projectmallard.org/1.0/"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="mal"
                version="1.0">


<!--!!==========================================================================
Mallard to XHTML

REMARK: Describe this module
-->

<xsl:import href="../../gettext/gettext.xsl"/>
<xsl:import href="../../common/color.xsl"/>
<xsl:import href="../../common/icons.xsl"/>
<xsl:import href="../../common/html.xsl"/>
<xsl:import href="../../common/utils.xsl"/>

<xsl:import href="../common/mal-gloss.xsl"/>
<xsl:import href="../common/mal-if.xsl"/>
<xsl:import href="../common/mal-link.xsl"/>

<xsl:param name="mal.if.env" select="'html xhtml'"/>
<xsl:param name="mal.link.extension" select="$html.extension"/>

<xsl:include href="mal2html-api.xsl"/>
<xsl:include href="mal2html-block.xsl"/>
<xsl:include href="mal2html-facets.xsl"/>
<xsl:include href="mal2html-gloss.xsl"/>
<xsl:include href="mal2html-inline.xsl"/>
<xsl:include href="mal2html-links.xsl"/>
<xsl:include href="mal2html-list.xsl"/>
<xsl:include href="mal2html-media.xsl"/>
<xsl:include href="mal2html-page.xsl"/>
<xsl:include href="mal2html-svg.xsl"/>
<xsl:include href="mal2html-table.xsl"/>
<xsl:include href="mal2html-ui.xsl"/>


</xsl:stylesheet>
