using System;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class QingdaoStaticSceneTests
    {
        Type Scene => TestReflection.FindAssemblyCSharpType("Sango.QingdaoStaticScene");

        [Test]
        public void ReadySceneStaysVisibleWhileNewCameraDetailLoads()
        {
            var root=new GameObject("Qingdao readiness integration");root.SetActive(false);
            var scene=root.AddComponent(Scene);
            try {
                var gate=(TwinLandscapeWarmup)Scene.GetField("m_Warmup",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(scene);
                gate.Begin("qingdao",0);gate.Observe(1,100,true,false);gate.Observe(5,100,true,false);
                var first=(TwinBridgeLandscapeState)Scene.GetMethod("Describe").Invoke(scene,null);
                Assert.That(first.ready,Is.True);
                gate.Observe(6,90,true,false);
                var moved=(TwinBridgeLandscapeState)Scene.GetMethod("Describe").Invoke(scene,null);
                Assert.That(moved.ready,Is.True,"Camera refinement must not hide the loaded geographic environment.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [Test]
        public void LocalTerrainCanBeShownWithoutClaimingCompletedOnlineWarmup()
        {
            var root=new GameObject("Qingdao preview");root.SetActive(false);
            var scene=root.AddComponent(Scene);
            var terrain=root.AddComponent<Terrain>();
            var flags=BindingFlags.Instance|BindingFlags.NonPublic;
            try {
                Scene.GetField("m_Terrain",flags).SetValue(scene,terrain);
                Scene.GetField("m_Opened",flags).SetValue(scene,true);
                var gate=(TwinLandscapeWarmup)Scene.GetField("m_Warmup",flags).GetValue(scene);
                gate.Begin("qingdao",0);
                var state=(TwinBridgeLandscapeState)Scene.GetMethod("Describe").Invoke(scene,null);
                Assert.That(state.displayable,Is.True);
                Assert.That(state.ready,Is.False);
                Assert.That(state.state,Is.EqualTo("warming"));
                Scene.GetField("m_Opened",flags).SetValue(scene,false);
                state=(TwinBridgeLandscapeState)Scene.GetMethod("Describe").Invoke(scene,null);
                Assert.That(state.displayable,Is.False);
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [Test]
        public void AbsoluteUtmMapsToEastAndNorthSceneAxes()
        {
            var geography=Activator.CreateInstance(Scene.GetNestedType("TerrainManifest"));
            geography.GetType().GetField("origin_e").SetValue(geography,256315d);
            geography.GetType().GetField("origin_n").SetValue(geography,3992326d);
            var result=(Vector3)Scene.GetMethod("LocalPosition").Invoke(null,new object[]{256415d,3992126d,geography});
            Assert.That(result,Is.EqualTo(new Vector3(100,0,-200)));
        }

        [Test]
        public void BundledHeightmapMatchesManifestAndContainsRelief()
        {
            var raw=Resources.Load<TextAsset>("Qingdao/heights");
            var manifest=Resources.Load<TextAsset>("Qingdao/terrain");
            Assert.That(raw,Is.Not.Null); Assert.That(manifest,Is.Not.Null);
            var bytes=raw.bytes;
            Assert.That(bytes.Length,Is.EqualTo(1025*1025*2));
            Assert.That(manifest.text,Does.Contain("EPSG:32651"));
            ushort min=ushort.MaxValue,max=0;
            for(int i=0;i<bytes.Length;i+=2)
            { var h=(ushort)(bytes[i] | bytes[i+1]<<8); min=Math.Min(min,h);max=Math.Max(max,h); }
            Assert.That(max-min,Is.GreaterThan(10000));
        }

        [Test]
        public void BundledLandMaskExposesWetRingsForTheWaterMaskOverlay()
        {
            var asset=Resources.Load<TextAsset>("Qingdao/land-mask");
            Assert.That(asset,Is.Not.Null,"Qingdao land-mask must ship in Resources");
            var maskType=Scene.GetNestedType("Mask",BindingFlags.NonPublic);
            var mask=JsonUtility.FromJson(asset.text,maskType);
            var flags=BindingFlags.Instance|BindingFlags.Public;
            var rings=(Array)maskType.GetField("rings",flags).GetValue(mask);
            var wetRings=(Array)maskType.GetField("wetRings",flags).GetValue(mask);
            Assert.That(rings.Length,Is.GreaterThan(0));
            Assert.That(wetRings,Is.Not.Null,"wetRings is the WaterMask overlay input (plan P0-B)");
            Assert.That(wetRings.Length,Is.GreaterThan(0));
            var ringType=Scene.GetNestedType("Ring",BindingFlags.NonPublic);
            var points=ringType.GetField("points",flags);
            foreach(var ring in new[]{rings,wetRings})
                for(int i=0;i<ring.Length;i++)
                    Assert.That(((Array)points.GetValue(ring.GetValue(i))).Length,Is.GreaterThanOrEqualTo(3));
        }

        [Test]
        public void QingdaoTilesetMaterialIsBundledBesideTheUntouchedNorwegianMaterial()
        {
            var qingdao=Resources.Load<Material>("Qingdao/QingdaoCesiumLandscapeMaterial");
            Assert.That(qingdao,Is.Not.Null,"Qingdao clone must ship in Resources (plan P0-B)");
            Assert.That(qingdao.HasProperty("_overlayTexture_WaterMask"),Is.True,
                "the WaterMask overlay channel must exist on the cloned shader graph");
            Assert.That(qingdao.HasProperty("_overlayTexture_Clipping"),Is.True,
                "the Cesium overlay protocol channels survive the clone");
            Assert.That(qingdao.IsKeywordEnabled("_ALPHATEST_ON"),Is.True,
                "alpha-test variant must be pre-enabled so player builds retain it");
            var norwegian=Resources.Load<Material>("TwinCesiumLandscapeMaterial");
            Assert.That(norwegian,Is.Not.Null);
            Assert.That(norwegian.HasProperty("_overlayTexture_WaterMask"),Is.False,
                "the shared Norwegian material stays on the unmodified upstream graph");
        }

        [Test]
        public void BundledShoreworkTableParsesWithManifestConsistentCounts()
        {
            var asset=Resources.Load<TextAsset>("Qingdao/shoreworks");
            Assert.That(asset,Is.Not.Null,"SLCONS shorework table must ship in Resources (plan P1-A)");
            var table=Scene.GetMethod("ParseShoreworks").Invoke(null,new object[]{asset.text});
            Assert.That(table,Is.Not.Null,"the bundled table must parse (strict parse, plan P1-A)");
            var tableType=table.GetType();
            Assert.That((string)tableType.GetField("schema").GetValue(table),Is.EqualTo("qingdao-shoreworks.v1"));
            Assert.That((string)tableType.GetField("assumption").GetValue(table),Does.Contain("视觉修整"));
            var features=(Array)tableType.GetField("features").GetValue(table);
            Assert.That(features,Is.Not.Null,"step: features array");
            Assert.That(features.Length,Is.GreaterThan(0));
            var featureType=Scene.GetNestedType("ShoreworkFeature");
            Assert.That(featureType,Is.Not.Null,"step: ShoreworkFeature nested type");
            var flags=BindingFlags.Instance|BindingFlags.Public;
            var kindField=featureType.GetField("kind",flags);
            var widthField=featureType.GetField("width_m",flags);
            var heightField=featureType.GetField("height_m",flags);
            var ringField=featureType.GetField("ring",flags);
            int lines=0,areas=0;
            foreach(var feature in features)
            {
                string kind=(string)kindField.GetValue(feature);
                var ring=(Array)ringField.GetValue(feature);
                Assert.That(ring,Is.Not.Null);
                Assert.That(ring.Length,Is.GreaterThanOrEqualTo(kind=="line"?2:3));
                Assert.That((float)heightField.GetValue(feature),Is.GreaterThan(0));
                foreach(var point in ring)
                {
                    var local=(Vector2)point;
                    Assert.That(Mathf.Abs(local.x),Is.LessThan(9100),"ring must stay inside the 18 km window");
                    Assert.That(Mathf.Abs(local.y),Is.LessThan(9100));
                }
                if(kind=="line") { lines++; Assert.That((float)widthField.GetValue(feature),Is.GreaterThan(0),"line features carry the assumed buffer width (plan D1=A)"); }
                else areas++;
            }
            var manifestAsset=Resources.Load<TextAsset>("Qingdao/terrain");
            Assert.That(manifestAsset,Is.Not.Null,"step: terrain manifest asset");
            var manifestType=Scene.GetNestedType("TerrainManifest");
            Assert.That(manifestType,Is.Not.Null,"step: TerrainManifest type");
            var manifest=JsonUtility.FromJson(manifestAsset.text,manifestType);
            Assert.That(manifest,Is.Not.Null,"step: manifest parse");
            var shoreworksField=manifestType.GetField("shoreworks",flags);
            Assert.That(shoreworksField,Is.Not.Null,"step: shoreworks field on manifest");
            var reference=shoreworksField.GetValue(manifest);
            Assert.That(reference,Is.Not.Null,"terrain.json records the bake-side shorework counts");
            var referenceType=reference.GetType();
            var linesField=referenceType.GetField("lines",flags);
            var areasField=referenceType.GetField("areas",flags);
            Assert.That(linesField,Is.Not.Null,"step: lines field");
            Assert.That(areasField,Is.Not.Null,"step: areas field");
            Assert.That(lines,Is.EqualTo((int)linesField.GetValue(reference)),
                "runtime table line count must match the manifest (currently 164)");
            Assert.That(areas,Is.EqualTo((int)areasField.GetValue(reference)),
                "runtime table area count must match the manifest (currently 51)");
        }

        [Test]
        public void ShoreworkMaterialsAreBundledForPlayerBuilds()
        {
            var concrete=Resources.Load<Material>("Qingdao/QingdaoShoreworkConcrete");
            var stone=Resources.Load<Material>("Qingdao/QingdaoShoreworkStone");
            Assert.That(concrete,Is.Not.Null,"serialized Lit materials pin the HDRP/Lit shader into player builds");
            Assert.That(stone,Is.Not.Null);
            foreach(var material in new[]{concrete,stone})
            {
                Assert.That(material.shader.name,Is.EqualTo("HDRP/Lit"));
                Assert.That(material.HasProperty("_BaseColor"),Is.True);
            }
        }

        [Test]
        public void ShoreworkMeshUsesLocalUtmFrameWithEmbeddedSkirt()
        {
            var featureType=Scene.GetNestedType("ShoreworkFeature");
            var flags=BindingFlags.Instance|BindingFlags.Public;
            float topLift=(float)Scene.GetField("k_ShoreworkTopLift",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
            float minDepth=(float)Scene.GetField("k_ShoreworkSkirtMinDepth",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
            float below=(float)Scene.GetField("k_ShoreworkSkirtBelowTerrain",BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
            var build=Scene.GetMethod("BuildShoreworkMesh");
            Func<Vector2,float> terrain=p=>1f;

            var line=Activator.CreateInstance(featureType);
            featureType.GetField("id",flags).SetValue(line,"TEST-LINE");
            featureType.GetField("kind",flags).SetValue(line,"line");
            featureType.GetField("type",flags).SetValue(line,"wharf");
            featureType.GetField("width_m",flags).SetValue(line,20f);
            featureType.GetField("height_m",flags).SetValue(line,6f);
            featureType.GetField("ring",flags).SetValue(line,new Vector2[]{new Vector2(100,200),new Vector2(150,200)});
            var lineMesh=(Mesh)build.Invoke(null,new object[]{line,terrain});
            Assert.That(lineMesh,Is.Not.Null);
            var lineVerts=lineMesh.vertices;
            Assert.That(lineMesh.triangles.Length,Is.GreaterThan(0));
            // east maps to +x, north to +z (LocalPosition frame, identity parent)
            foreach(var corner in new[]{new Vector2(100,190),new Vector2(100,210),new Vector2(150,190),new Vector2(150,210)})
                Assert.That(lineVerts.Any(v=>Mathf.Abs(v.x-corner.x)<0.01f&&Mathf.Abs(v.z-corner.y)<0.01f),
                    $"buffered corner {corner} missing — width buffer must offset ±width/2");
            Assert.That(lineVerts.Max(v=>v.y),Is.EqualTo(6f+topLift).Within(0.001f),"deck sits at the assumed height plus the anti-z-fight lift");
            Assert.That(lineVerts.Min(v=>v.y),Is.EqualTo(Mathf.Min(6f+topLift-minDepth,1f-below)).Within(0.001f),
                "tooth-embed skirt reaches below the sampled terrain");

            var area=Activator.CreateInstance(featureType);
            featureType.GetField("id",flags).SetValue(area,"TEST-AREA");
            featureType.GetField("kind",flags).SetValue(area,"area");
            featureType.GetField("type",flags).SetValue(area,"slipway");
            featureType.GetField("height_m",flags).SetValue(area,4f);
            featureType.GetField("ring",flags).SetValue(area,new Vector2[]{new Vector2(0,0),new Vector2(30,0),new Vector2(30,20),new Vector2(0,20)});
            var areaMesh=(Mesh)build.Invoke(null,new object[]{area,terrain});
            Assert.That(areaMesh,Is.Not.Null);
            var areaVerts=areaMesh.vertices;
            foreach(var corner in new[]{new Vector2(0,0),new Vector2(30,0),new Vector2(30,20),new Vector2(0,20)})
                Assert.That(areaVerts.Any(v=>Mathf.Abs(v.x-corner.x)<0.01f&&Mathf.Abs(v.z-corner.y)<0.01f),
                    $"area corner {corner} missing — areas extrude their digitised footprint");
            Assert.That(areaVerts.Max(v=>v.y),Is.EqualTo(4f+topLift).Within(0.001f));
            UnityEngine.Object.DestroyImmediate(lineMesh);
            UnityEngine.Object.DestroyImmediate(areaMesh);
        }

        [Test]
        public void ShoreworkTerrainSamplerMapsWindowAxesAndScale()
        {
            var manifestType=Scene.GetNestedType("TerrainManifest");
            var flags=BindingFlags.Instance|BindingFlags.Public;
            var geography=Activator.CreateInstance(manifestType);
            manifestType.GetField("size_m",flags).SetValue(geography,100f);
            manifestType.GetField("base_y",flags).SetValue(geography,-10f);
            manifestType.GetField("range_y",flags).SetValue(geography,20f);
            var sampler=Scene.GetMethod("ShoreworkTerrainHeight");
            float Sample(float[,] grid,Vector2 local)=>(float)sampler.Invoke(null,new object[]{geography,grid,local});

            // Pure-array fixtures at the sampler seam. Grid layout follows
            // BuildTerrain/bake: first index south→north, second west→east.
            var eastGrid=new float[5,5];
            for(int a=0;a<5;a++) eastGrid[a,4]=1f; // east edge column high
            Assert.That(Sample(eastGrid,new Vector2(40,0)),Is.GreaterThan(Sample(eastGrid,new Vector2(-40,0))),
                "u must follow +east (ring x)");
            Assert.That(Sample(eastGrid,new Vector2(-45,0)),Is.EqualTo(-10f).Within(0.01f),"flat zero cells sample to base_y");

            var northGrid=new float[5,5];
            for(int b=0;b<5;b++) northGrid[4,b]=1f; // north edge row high
            Assert.That(Sample(northGrid,new Vector2(0,40)),Is.GreaterThan(Sample(northGrid,new Vector2(0,-40))),
                "v must follow +north (ring y)");

            var uniformGrid=new float[5,5];
            for(int a=0;a<5;a++) for(int b=0;b<5;b++) uniformGrid[a,b]=0.5f;
            Assert.That(Sample(uniformGrid,Vector2.zero),Is.EqualTo(0f).Within(0.01f),
                "heights must come back scaled by range_y (base -10 + 0.5*20 = 0)");

            // Integration through real TerrainData at a valid heightmap
            // resolution (2^k+1) — the production path is resolution 1025.
            // NOTE: heightmapResolution=3 is silently ignored (property stays
            // 33), which is why the grid fixtures above are hand-built.
            var data=new TerrainData { heightmapResolution=65, size=new Vector3(100,20,100) };
            var heights=new float[65,65];
            for(int a=0;a<65;a++) heights[a,64]=1f; // east edge high
            data.SetHeights(0,0,heights);
            var readGrid=Scene.GetMethod("ReadShoreworkHeightGrid");
            var grid=(float[,])readGrid.Invoke(null,new object[]{data});
            Assert.That(grid.GetLength(0),Is.EqualTo(65));
            // one cell from the edge: 100 m / 64 cells = 1.5625 m per cell, so
            // +49 m lands inside the last interpolation cell (cols 63/64).
            Assert.That(Sample(grid,new Vector2(49,0)),Is.GreaterThan(Sample(grid,new Vector2(-49,0))),
                "the TerrainData-backed grid must keep the bake axis order");
            UnityEngine.Object.DestroyImmediate(data);
        }

        [Test]
        public void ShoreWaterAbsorptionTunesOnEntryAndRestoresOnClear()
        {
            var root=new GameObject("Qingdao water tuning");root.SetActive(false);
            var scene=root.AddComponent(Scene);
            var waterGo=new GameObject("Qingdao water tuning surface");
            var waterType=System.Type.GetType("UnityEngine.Rendering.HighDefinition.WaterSurface,Unity.RenderPipelines.HighDefinition.Runtime");
            Assert.That(waterType,Is.Not.Null,"HDRP WaterSurface type must resolve");
            var water=waterGo.AddComponent(waterType);
            var absorption=waterType.GetField("absorptionDistance");
            absorption.SetValue(water,5f); // serialized SangoTwin value
            var flags=BindingFlags.Instance|BindingFlags.NonPublic;
            Environment.SetEnvironmentVariable("TWIN_QINGDAO_WATER_ABSORPTION","16");
            try {
                Scene.GetMethod("ApplyShoreWaterTuning",flags).Invoke(scene,null);
                Assert.That((float)absorption.GetValue(water),Is.EqualTo(16f).Within(0.01f),
                    "entry retunes absorption so the shallow imagery band fades into deep water");
                Assert.That((float)Scene.GetField("m_PreviousWaterAbsorption",flags).GetValue(scene),Is.EqualTo(5f).Within(0.001f));
                Scene.GetMethod("ApplyShoreWaterTuning",flags).Invoke(scene,null);
                Assert.That((float)absorption.GetValue(water),Is.EqualTo(16f).Within(0.01f),"re-entry while in charge keeps the tuned value");
                Scene.GetMethod("RestoreShoreWaterTuning",flags).Invoke(scene,null);
                Assert.That((float)absorption.GetValue(water),Is.EqualTo(5f).Within(0.001f),
                    "clear restores the serialized value (the Norwegian link shares this surface)");
            }
            finally {
                Environment.SetEnvironmentVariable("TWIN_QINGDAO_WATER_ABSORPTION",null);
                UnityEngine.Object.DestroyImmediate(waterGo);
                UnityEngine.Object.DestroyImmediate(root);
            }
        }

        [Test]
        public void ClearHidesShoreworksAndReentryReshowsThem()
        {
            var root=new GameObject("Qingdao shorework lifecycle");root.SetActive(false);
            var scene=root.AddComponent(Scene);
            var instanceFlags=BindingFlags.Instance|BindingFlags.NonPublic;
            var geoRoot=new GameObject("geo root");
            var shoreRoot=new GameObject("Qingdao shoreworks");
            shoreRoot.transform.SetParent(geoRoot.transform,false);
            var volume=new GameObject("Qingdao shorework CN TEST pier");
            volume.transform.SetParent(shoreRoot.transform,false);
            var filter=volume.AddComponent<MeshFilter>();
            filter.sharedMesh=new Mesh();
            volume.AddComponent<MeshRenderer>();
            var driverGo=new GameObject("Qingdao shorework driver stub");
            var geography=Activator.CreateInstance(Scene.GetNestedType("TerrainManifest"));
            Scene.GetProperty("Geography").GetSetMethod(true).Invoke(scene,new[]{geography});
            try {
                Scene.GetField("m_Root",instanceFlags).SetValue(scene,geoRoot);
                Scene.GetField("m_ShoreworkRoot",instanceFlags).SetValue(scene,shoreRoot);
                Scene.GetField("m_Opened",instanceFlags).SetValue(scene,true);
                Scene.GetMethod("Clear").Invoke(scene,null);
                Assert.That(shoreRoot.activeSelf,Is.False,"Clear must auto-hide the shore volumes (plan P1-A lifecycle)");
                Assert.That(volume.GetComponent<MeshRenderer>().enabled,Is.False);

                Scene.GetField("m_Opened",instanceFlags).SetValue(scene,false);
                // phase-1 satellite-first (2026-10-21): volumes default off; the
                // lifecycle contract under test is re-entry restoring the retained
                // rig, so simulate the TWIN_QINGDAO_SHOREWORKS=1 opt-in state.
                Scene.GetField("m_ShoreworksEnabled",instanceFlags).SetValue(scene,true);
                var driverType=TestReflection.FindAssemblyCSharpType("Sango.TwinSessionDriver");
                // Open(driver, camera, bool staticView = true):反射 Invoke 不走默认参填充,
                // 第 3 参用 Type.Missing 让 binder 取默认值(phase-1 演进加参,签名 3 参)。
                Scene.GetMethod("Open").Invoke(scene,new object[]{driverGo.AddComponent(driverType),null,Type.Missing});
                Assert.That(shoreRoot.activeSelf,Is.True,"re-entry must re-show the retained shore volumes");
                Assert.That(volume.GetComponent<MeshRenderer>().enabled,Is.True);
            }
            finally {
                UnityEngine.Object.DestroyImmediate(filter.sharedMesh);
                UnityEngine.Object.DestroyImmediate(root);
                UnityEngine.Object.DestroyImmediate(geoRoot);
                UnityEngine.Object.DestroyImmediate(driverGo);
            }
        }
    }
}
