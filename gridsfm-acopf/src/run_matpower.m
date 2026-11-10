function run_matpower(listfile, outdir)
  addpath(genpath('repos/matpower'));
  if ~exist(outdir, 'dir'); mkdir(outdir); end
  fid = fopen(listfile, 'r');
  if fid < 0; error('cannot open %s', listfile); end
  C = textscan(fid, '%s %s', 'Delimiter', ',', 'CommentStyle', '#');
  fclose(fid);
  ids = C{1}; paths = C{2};
  mpopt = mpoption('verbose', 0, 'out.all', 0);
  mpopt = mpoption(mpopt, 'opf.violation', 1e-8, 'mips.feastol', 1e-8, ...
    'mips.gradtol', 1e-8, 'mips.comptol', 1e-8, 'mips.costtol', 1e-8);
  mpopt = mpoption(mpopt, 'opf.flow_lim', 'S');
  for i = 1:numel(ids)
    sid = ids{i}; cpath = paths{i};
    fprintf('MP %s\n', sid);
    outp = fullfile(outdir, [sid '.json']);
    if exist(outp, 'file'); fprintf('  skip existing\n'); continue; end
    try
      mpc = loadcase(cpath);
      % force ang limits
      if size(mpc.branch,2) >= 13
        mpc.branch(:,12) = -60; mpc.branch(:,13) = 60;
      end
      t0 = tic;
      r = runopf(mpc, mpopt);
      wall = toc(t0);
      write_result(outp, sid, r, wall);
      fprintf('  success=%d f=%.4f et=%.3f\n', r.success, r.f, r.et);
    catch err
      fid2 = fopen(outp, 'w');
      fprintf(fid2, '{"scenario_id":"%s","tool":"MATPOWER/MIPS","solved":false,"termination_status":"ERROR","error":"%s","objective":null,"solve_time":null,"wall_time":null}', sid, strrep(err.message,'"','\"'));
      fclose(fid2);
      fprintf('  ERROR %s\n', err.message);
    end
  end
end

function write_result(outp, sid, r, wall)
  fid = fopen(outp, 'w');
  fprintf(fid, '{');
  fprintf(fid, '"scenario_id":"%s",', sid);
  fprintf(fid, '"tool":"MATPOWER/MIPS",');
  fprintf(fid, '"solved":%s,', tern(r.success, 'true', 'false'));
  fprintf(fid, '"termination_status":"%s",', tern(r.success, 'SUCCESS', 'FAIL'));
  fprintf(fid, '"objective":%.10g,', r.f);
  fprintf(fid, '"solve_time":%.10g,', r.et);
  fprintf(fid, '"wall_time":%.10g,', wall);
  fprintf(fid, '"baseMVA":%.10g,', r.baseMVA);
  % buses
  fprintf(fid, '"bus":{');
  for i=1:size(r.bus,1)
    if i>1; fprintf(fid, ','); end
    fprintf(fid, '"%d":{"vm":%.10g,"va_deg":%.10g}', r.bus(i,1), r.bus(i,8), r.bus(i,9));
  end
  fprintf(fid, '},');
  fprintf(fid, '"gen":{');
  for i=1:size(r.gen,1)
    if i>1; fprintf(fid, ','); end
    fprintf(fid, '"%d":{"pg":%.10g,"qg":%.10g,"gen_bus":%d,"status":%d}', i, r.gen(i,2), r.gen(i,3), r.gen(i,1), r.gen(i,8));
  end
  fprintf(fid, '}');
  fprintf(fid, '}');
  fclose(fid);
end

function s = tern(c, a, b)
  if c; s=a; else; s=b; end
end
